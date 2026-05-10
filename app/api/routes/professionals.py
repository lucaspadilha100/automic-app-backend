from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid
from datetime import datetime, timezone

from db.session import get_db
from app.core.dependencies import (
    get_current_user, require_active_tenant, require_manager_or_above,
    require_tenant_owner_or_above,
)
from app.core.exceptions import NotFoundError, ProfessionalNotFoundError
from app.core.security import hash_password
from pydantic import BaseModel
from app.models.user import User
from app.models.tenant import Tenant
from app.models.professional import Professional, ProfessionalAvailability
from app.models.service import ProfessionalService, Service
from app.models.schedule import BusinessHour, BlockedTime
from app.models.appointment import Appointment
from app.services.plan_limit_service import plan_limit_service
from app.services.audit_service import audit_service
from app.schemas.schemas import (
    ProfessionalCreate, ProfessionalUpdate, ProfessionalResponse,
    ProfessionalServiceLink, AvailabilityCreate,
    BusinessHourCreate, BusinessHourResponse,
    BlockedTimeCreate, BlockedTimeResponse,
)

router = APIRouter(prefix="/professionals", tags=["Profissionais"])


# ---- Professional self appointments (must be before /{professional_id} wildcard) ----

def _serialize_appt(a):
    return {
        "id": str(a.id),
        "start_datetime": a.start_datetime.isoformat(),
        "end_datetime": a.end_datetime.isoformat() if a.end_datetime else None,
        "status": a.status,
        "customer_notes": a.customer_notes,
        "services": [s.service_name_snapshot for s in (a.appointment_services or [])],
        "customer_name": a.customer_account.name if a.customer_account else None,
        "customer_phone": a.customer_account.phone if a.customer_account else None,
    }


@router.get("/me/appointments")
def get_my_appointments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "professional":
        raise HTTPException(status_code=403, detail="Apenas profissionais podem acessar este recurso.")
    prof = db.query(Professional).filter(Professional.user_id == current_user.id).first()
    if not prof:
        raise HTTPException(status_code=404, detail="Profissional não encontrado para este usuário.")
    appointments = db.query(Appointment).filter(
        Appointment.professional_id == prof.id,
    ).order_by(Appointment.start_datetime.desc()).limit(100).all()
    return [_serialize_appt(a) for a in appointments]



def create_professional(
    payload: ProfessionalCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    plan_limit_service.check_professional_limit(db, tenant)
    prof = Professional(tenant_id=tenant.id, **payload.model_dump())
    db.add(prof)
    db.flush()
    audit_service.log(db, "professional_created", "professional", prof.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(prof)
    return prof


@router.get("", response_model=List[ProfessionalResponse])
def list_professionals(
    active_only: bool = True,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Professional).filter(
        Professional.tenant_id == tenant.id, Professional.deleted_at.is_(None)
    )
    if active_only:
        q = q.filter(Professional.is_active == True)
    return q.all()


@router.get("/{professional_id}", response_model=ProfessionalResponse)
def get_professional(
    professional_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prof = db.query(Professional).filter(
        Professional.id == professional_id,
        Professional.tenant_id == tenant.id,
        Professional.deleted_at.is_(None),
    ).first()
    if not prof:
        raise ProfessionalNotFoundError()
    return prof


@router.put("/{professional_id}", response_model=ProfessionalResponse)
def update_professional(
    professional_id: uuid.UUID,
    payload: ProfessionalUpdate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    prof = db.query(Professional).filter(
        Professional.id == professional_id,
        Professional.tenant_id == tenant.id,
        Professional.deleted_at.is_(None),
    ).first()
    if not prof:
        raise ProfessionalNotFoundError()
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(prof, k, v)
    audit_service.log(db, "professional_updated", "professional", prof.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(prof)
    return prof


@router.delete("/{professional_id}")
def delete_professional(
    professional_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    prof = db.query(Professional).filter(
        Professional.id == professional_id,
        Professional.tenant_id == tenant.id,
        Professional.deleted_at.is_(None),
    ).first()
    if not prof:
        raise ProfessionalNotFoundError()
    prof.deleted_at = datetime.now(timezone.utc)
    prof.is_active = False
    audit_service.log(db, "professional_deleted", "professional", prof.id, tenant.id, current_user.id)
    db.commit()
    return {"message": "Profissional removido."}


# ---- Services link ----

@router.put("/{professional_id}/services")
def set_professional_services(
    professional_id: uuid.UUID,
    payload: ProfessionalServiceLink,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    prof = db.query(Professional).filter(
        Professional.id == professional_id, Professional.tenant_id == tenant.id
    ).first()
    if not prof:
        raise ProfessionalNotFoundError()

    # Validate all service IDs belong to tenant
    svcs = db.query(Service).filter(
        Service.id.in_(payload.service_ids),
        Service.tenant_id == tenant.id,
        Service.deleted_at.is_(None),
    ).all()
    if len(svcs) != len(payload.service_ids):
        raise NotFoundError("SERVICE_NOT_FOUND", "Um ou mais serviços não encontrados.")

    # Replace all links
    db.query(ProfessionalService).filter(
        ProfessionalService.professional_id == professional_id,
        ProfessionalService.tenant_id == tenant.id,
    ).delete()

    for svc in svcs:
        link = ProfessionalService(
            tenant_id=tenant.id,
            professional_id=professional_id,
            service_id=svc.id,
            created_at=datetime.now(timezone.utc),
        )
        db.add(link)

    audit_service.log(db, "professional_services_updated", "professional", prof.id, tenant.id, current_user.id)
    db.commit()
    return {"message": "Serviços vinculados atualizados.", "service_ids": [str(s.id) for s in svcs]}


@router.get("/{professional_id}/services")
def get_professional_services(
    professional_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    links = db.query(ProfessionalService).filter(
        ProfessionalService.professional_id == professional_id,
        ProfessionalService.tenant_id == tenant.id,
    ).all()
    return {"service_ids": [str(lk.service_id) for lk in links]}


# ---- Availability (weekly schedule) ----

@router.put("/{professional_id}/availability")
def set_availability(
    professional_id: uuid.UUID,
    payload: List[AvailabilityCreate],
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    prof = db.query(Professional).filter(
        Professional.id == professional_id, Professional.tenant_id == tenant.id
    ).first()
    if not prof:
        raise ProfessionalNotFoundError()

    db.query(ProfessionalAvailability).filter(
        ProfessionalAvailability.professional_id == professional_id,
        ProfessionalAvailability.tenant_id == tenant.id,
    ).delete()

    from datetime import time as t_type
    for slot in payload:
        def parse_time(s: Optional[str]):
            if not s:
                return None
            h, m = s.split(":")
            return t_type(int(h), int(m))

        pa = ProfessionalAvailability(
            tenant_id=tenant.id,
            professional_id=professional_id,
            weekday=slot.weekday,
            start_time=parse_time(slot.start_time),
            end_time=parse_time(slot.end_time),
            break_start_time=parse_time(slot.break_start_time),
            break_end_time=parse_time(slot.break_end_time),
            is_available=slot.is_available,
        )
        db.add(pa)

    db.commit()
    return {"message": "Disponibilidade atualizada."}


@router.get("/{professional_id}/availability")
def get_availability(
    professional_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(ProfessionalAvailability).filter(
        ProfessionalAvailability.professional_id == professional_id,
        ProfessionalAvailability.tenant_id == tenant.id,
    ).order_by(ProfessionalAvailability.weekday).all()
    return rows


# ---- Enable login ----

class EnableLoginRequest(BaseModel):
    login_email: str
    password: str


@router.post("/{professional_id}/enable-login")
def enable_professional_login(
    professional_id: uuid.UUID,
    payload: EnableLoginRequest,
    current_user: User = Depends(require_tenant_owner_or_above),
    db: Session = Depends(get_db),
):
    prof = db.query(Professional).filter(
        Professional.id == professional_id,
        Professional.tenant_id == current_user.tenant_id,
        Professional.deleted_at.is_(None),
    ).first()
    if not prof:
        raise ProfessionalNotFoundError()

    # Check if another professional in the same tenant already uses this email
    conflict = db.query(Professional).join(
        User, Professional.user_id == User.id
    ).filter(
        Professional.tenant_id == current_user.tenant_id,
        User.email == payload.login_email,
        Professional.id != professional_id,
    ).first()
    if conflict:
        raise HTTPException(status_code=409, detail="Email already in use by another professional in this tenant.")

    if prof.user_id is not None:
        # Update existing user
        existing_user = db.query(User).filter(User.id == prof.user_id).first()
        if existing_user:
            existing_user.email = payload.login_email
            existing_user.password_hash = hash_password(payload.password)
            db.commit()
        return {"updated": True}
    else:
        # Create new user
        new_user = User(
            role="professional",
            tenant_id=prof.tenant_id,
            email=payload.login_email,
            password_hash=hash_password(payload.password),
            name=prof.name,
            is_active=True,
        )
        db.add(new_user)
        db.flush()
        prof.user_id = new_user.id
        db.commit()
        return {"created": True, "user_id": str(new_user.id)}

