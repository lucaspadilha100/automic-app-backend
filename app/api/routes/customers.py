from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import uuid

from db.session import get_db
from app.core.dependencies import (
    get_current_user, require_active_tenant, require_receptionist_or_above,
    require_manager_or_above,
)
from app.core.exceptions import NotFoundError, ConflictError, CustomerNotFoundError, ValidationError
from app.models.user import User
from app.models.tenant import Tenant
from app.models.customer import (
    CustomerAccount, TenantCustomer, CustomerTag, CustomerTagLink, CustomerNote
)
from app.models.appointment import Appointment
from app.models.procedure import ProcedureHistory
from app.models.package import CustomerPackage
from app.services.audit_service import audit_service
from app.services.customer_event_service import customer_event_service
from app.schemas.schemas import (
    CustomerNoteCreate, CustomerTagCreate,
    ProcedureHistoryCreate, ProcedureHistoryResponse,
    CustomerPackageCreate, CustomerPackageResponse,
)
from app.core.security import hash_password

router = APIRouter(prefix="/customers", tags=["Clientes"])


def _get_tenant_customer(tenant_customer_id: uuid.UUID, tenant: Tenant, db: Session) -> TenantCustomer:
    tc = db.query(TenantCustomer).filter(
        TenantCustomer.id == tenant_customer_id,
        TenantCustomer.tenant_id == tenant.id,
    ).first()
    if not tc:
        raise CustomerNotFoundError()
    return tc


@router.get("")
def list_customers(
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(50, le=200),
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (
        db.query(TenantCustomer, CustomerAccount)
        .join(CustomerAccount, TenantCustomer.customer_account_id == CustomerAccount.id)
        .filter(TenantCustomer.tenant_id == tenant.id)
    )
    if search:
        q = q.filter(
            (CustomerAccount.name.ilike(f"%{search}%")) |
            (CustomerAccount.phone.ilike(f"%{search}%")) |
            (CustomerAccount.email.ilike(f"%{search}%"))
        )
    rows = q.offset(skip).limit(limit).all()
    result = []
    for tc, ca in rows:
        result.append({
            "id": str(tc.id),
            "customer_account_id": str(ca.id),
            "name": ca.name,
            "phone": ca.phone,
            "email": ca.email,
            "cpf": tc.cpf,
            "birth_date": tc.birth_date.isoformat() if tc.birth_date else None,
            "created_at": tc.created_at.isoformat(),
        })
    return result


@router.post("")
def create_or_link_customer(
    name: str,
    phone: str,
    email: Optional[str] = None,
    cpf: Optional[str] = None,
    notes: Optional[str] = None,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    """Find or create global CustomerAccount and link to this tenant."""
    ca = db.query(CustomerAccount).filter(CustomerAccount.phone == phone).first()
    if not ca:
        import secrets
        ca = CustomerAccount(
            name=name,
            phone=phone,
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(16)),
        )
        db.add(ca)
        db.flush()

    tc = db.query(TenantCustomer).filter(
        TenantCustomer.tenant_id == tenant.id,
        TenantCustomer.customer_account_id == ca.id,
    ).first()

    if not tc:
        tc = TenantCustomer(
            tenant_id=tenant.id,
            customer_account_id=ca.id,
            cpf=cpf,
            notes=notes,
        )
        db.add(tc)
        db.flush()
        customer_event_service.emit(
            db, "customer_created", tenant.id, ca.id, tc.id, "tenant_customer", tc.id
        )
        audit_service.log(db, "customer_created", "tenant_customer", tc.id, tenant.id, current_user.id)

    db.commit()
    db.refresh(tc)
    return {"id": str(tc.id), "customer_account_id": str(ca.id), "name": ca.name, "phone": ca.phone}


@router.get("/{tenant_customer_id}")
def get_customer(
    tenant_customer_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tc = _get_tenant_customer(tenant_customer_id, tenant, db)
    ca = tc.customer_account
    return {
        "id": str(tc.id),
        "customer_account_id": str(ca.id),
        "name": ca.name,
        "phone": ca.phone,
        "email": ca.email,
        "cpf": tc.cpf,
        "birth_date": tc.birth_date.isoformat() if tc.birth_date else None,
        "internal_notes": tc.internal_notes,
        "notes": tc.notes,
        "marketing_consent": tc.marketing_consent,
        "created_at": tc.created_at.isoformat(),
    }


@router.put("/{tenant_customer_id}")
def update_customer(
    tenant_customer_id: uuid.UUID,
    cpf: Optional[str] = None,
    notes: Optional[str] = None,
    internal_notes: Optional[str] = None,
    marketing_consent: Optional[bool] = None,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    tc = _get_tenant_customer(tenant_customer_id, tenant, db)
    if cpf is not None:
        tc.cpf = cpf
    if notes is not None:
        tc.notes = notes
    if internal_notes is not None:
        tc.internal_notes = internal_notes
    if marketing_consent is not None:
        tc.marketing_consent = marketing_consent
    audit_service.log(db, "customer_updated", "tenant_customer", tc.id, tenant.id, current_user.id)
    db.commit()
    return {"message": "Cliente atualizado."}


# ---- Notes ----

@router.post("/{tenant_customer_id}/notes")
def add_note(
    tenant_customer_id: uuid.UUID,
    payload: CustomerNoteCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    tc = _get_tenant_customer(tenant_customer_id, tenant, db)
    note_data = payload.model_dump(exclude_none=True)
    content = note_data.get("content") or note_data.get("note")
    if not content:
        raise ValidationError("A nota não pode ficar vazia.")
    visibility = note_data.get("visibility") or ("internal" if note_data.get("is_internal", True) else "customer_visible")
    if visibility not in ("internal", "customer_visible"):
        raise ValidationError("visibility deve ser internal ou customer_visible.")
    note = CustomerNote(
        tenant_id=tenant.id,
        tenant_customer_id=tc.id,
        created_by_user_id=current_user.id,
        content=content,
        note=content,
        is_internal=(visibility == "internal"),
        visibility=visibility,
        note_type=note_data.get("note_type", "manual"),
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.get("/{tenant_customer_id}/notes")
def list_notes(
    tenant_customer_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tc = _get_tenant_customer(tenant_customer_id, tenant, db)
    return tc.customer_notes


# ---- Tags ----

@router.post("/tags", tags=["Clientes - Tags"])
def create_tag(
    payload: CustomerTagCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    tag = CustomerTag(tenant_id=tenant.id, **payload.model_dump())
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.get("/tags", tags=["Clientes - Tags"])
def list_tags(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(CustomerTag).filter(CustomerTag.tenant_id == tenant.id, CustomerTag.is_active == True).all()


@router.post("/{tenant_customer_id}/tags/{tag_id}", tags=["Clientes - Tags"])
def link_tag(
    tenant_customer_id: uuid.UUID,
    tag_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    tc = _get_tenant_customer(tenant_customer_id, tenant, db)
    tag = db.query(CustomerTag).filter(CustomerTag.id == tag_id, CustomerTag.tenant_id == tenant.id).first()
    if not tag:
        raise NotFoundError("TAG_NOT_FOUND", "Tag não encontrada.")
    exists = db.query(CustomerTagLink).filter(
        CustomerTagLink.tenant_id == tenant.id,
        CustomerTagLink.tenant_customer_id == tc.id,
        CustomerTagLink.tag_id == tag_id,
    ).first()
    if not exists:
        link = CustomerTagLink(
            tenant_id=tenant.id,
            tenant_customer_id=tc.id,
            tag_id=tag_id,
            created_at=datetime.now(timezone.utc),
        )
        db.add(link)
        db.commit()
    return {"message": "Tag vinculada."}


@router.delete("/{tenant_customer_id}/tags/{tag_id}", tags=["Clientes - Tags"])
def unlink_tag(
    tenant_customer_id: uuid.UUID,
    tag_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    tc = _get_tenant_customer(tenant_customer_id, tenant, db)
    db.query(CustomerTagLink).filter(
        CustomerTagLink.tenant_id == tenant.id,
        CustomerTagLink.tenant_customer_id == tc.id,
        CustomerTagLink.tag_id == tag_id,
    ).delete()
    db.commit()
    return {"message": "Tag desvinculada."}


# ---- Procedure History ----

@router.post("/{tenant_customer_id}/procedures", response_model=ProcedureHistoryResponse, tags=["Prontuário"])
def create_procedure(
    tenant_customer_id: uuid.UUID,
    payload: ProcedureHistoryCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    tc = _get_tenant_customer(tenant_customer_id, tenant, db)
    ph = ProcedureHistory(
        tenant_id=tenant.id,
        tenant_customer_id=tc.id,
        customer_account_id=tc.customer_account_id,
        created_by_user_id=current_user.id,
        **payload.model_dump(),
    )
    db.add(ph)
    db.commit()
    db.refresh(ph)
    return ph


@router.get("/{tenant_customer_id}/procedures", response_model=List[ProcedureHistoryResponse], tags=["Prontuário"])
def list_procedures(
    tenant_customer_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tc = _get_tenant_customer(tenant_customer_id, tenant, db)
    return tc.procedure_history


# ---- Customer Appointments ----

@router.get("/{tenant_customer_id}/appointments")
def customer_appointments(
    tenant_customer_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tc = _get_tenant_customer(tenant_customer_id, tenant, db)
    return tc.appointments


# ---- Customer Packages ----

@router.post("/{tenant_customer_id}/packages", response_model=CustomerPackageResponse, tags=["Pacotes"])
def assign_package(
    tenant_customer_id: uuid.UUID,
    payload: CustomerPackageCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    from app.models.package import Package, CustomerPackage
    from app.services.plan_limit_service import plan_limit_service
    from datetime import timedelta

    plan_limit_service.check_package_limit(db, tenant)

    pkg = db.query(Package).filter(Package.id == payload.package_id, Package.tenant_id == tenant.id).first()
    if not pkg:
        from app.core.exceptions import PackageNotFoundError
        raise PackageNotFoundError()

    tc = _get_tenant_customer(tenant_customer_id, tenant, db)

    cp = CustomerPackage(
        tenant_id=tenant.id,
        customer_account_id=tc.customer_account_id,
        tenant_customer_id=tc.id,
        package_id=pkg.id,
        total_sessions=pkg.total_sessions,
        used_sessions=0,
        remaining_sessions=pkg.total_sessions,
        status="active",
        payment_status=payload.payment_status,
        price_paid=payload.price_paid or pkg.price,
        purchase_price=payload.price_paid or pkg.price,
        created_by_user_id=current_user.id,
        notes=payload.notes,
        starts_at=datetime.now(timezone.utc),
        expires_at=(
            datetime.now(timezone.utc) + timedelta(days=pkg.validity_days)
            if pkg.validity_days else None
        ),
    )
    db.add(cp)
    audit_service.log(db, "customer_package_created", "customer_package", cp.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(cp)
    return cp


@router.get("/{tenant_customer_id}/packages", response_model=List[CustomerPackageResponse], tags=["Pacotes"])
def list_customer_packages(
    tenant_customer_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tc = _get_tenant_customer(tenant_customer_id, tenant, db)
    return tc.customer_packages
