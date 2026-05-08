from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid

from db.session import get_db
from app.core.dependencies import (
    get_current_user, require_active_tenant, require_manager_or_above,
    require_receptionist_or_above,
)
from app.core.exceptions import UnitNotFoundError, NotFoundError
from app.models.user import User
from app.models.tenant import Tenant
from app.models.unit import Unit
from app.models.waitlist import WaitlistEntry
from app.services.plan_limit_service import plan_limit_service
from app.services.feature_flag_service import feature_flag_service
from app.services.audit_service import audit_service
from app.schemas.schemas import UnitCreate, UnitResponse

# ---- Units ----

units_router = APIRouter(prefix="/units", tags=["Unidades"])


@units_router.post("", response_model=UnitResponse)
def create_unit(
    payload: UnitCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    existing_units = db.query(Unit).filter(
        Unit.tenant_id == tenant.id,
        Unit.deleted_at.is_(None),
    ).count()

    # The first/main unit is mandatory and allowed even without the multi_unit
    # feature. Extra units require the feature flag and plan limit.
    if existing_units > 0:
        feature_flag_service.require_feature(db, tenant, "multi_unit")
        plan_limit_service.check_unit_limit(db, tenant)

    data = payload.model_dump()
    if existing_units == 0:
        data["is_main"] = True

    unit = Unit(tenant_id=tenant.id, **data)
    db.add(unit)
    db.flush()
    audit_service.log(db, "unit_created", "unit", unit.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(unit)
    return unit


@units_router.get("", response_model=List[UnitResponse])
def list_units(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(Unit).filter(
        Unit.tenant_id == tenant.id, Unit.deleted_at.is_(None), Unit.is_active == True
    ).all()


@units_router.get("/{unit_id}", response_model=UnitResponse)
def get_unit(
    unit_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    unit = db.query(Unit).filter(Unit.id == unit_id, Unit.tenant_id == tenant.id).first()
    if not unit:
        raise UnitNotFoundError()
    return unit


@units_router.put("/{unit_id}", response_model=UnitResponse)
def update_unit(
    unit_id: uuid.UUID,
    payload: UnitCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    unit = db.query(Unit).filter(Unit.id == unit_id, Unit.tenant_id == tenant.id).first()
    if not unit:
        raise UnitNotFoundError()
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(unit, k, v)
    db.commit()
    db.refresh(unit)
    return unit


@units_router.delete("/{unit_id}")
def delete_unit(
    unit_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    unit = db.query(Unit).filter(Unit.id == unit_id, Unit.tenant_id == tenant.id).first()
    if not unit:
        raise UnitNotFoundError()
    if unit.is_main:
        from app.core.exceptions import ValidationError
        raise ValidationError("Não é possível remover a unidade principal.")
    unit.deleted_at = datetime.now(timezone.utc)
    unit.is_active = False
    db.commit()
    return {"message": "Unidade removida."}


# ---- Waitlist ----

waitlist_router = APIRouter(prefix="/waitlist", tags=["Lista de Espera"])


@waitlist_router.post("")
def add_to_waitlist(
    customer_account_id: uuid.UUID,
    service_ids: Optional[List[uuid.UUID]] = None,
    preferred_professional_id: Optional[uuid.UUID] = None,
    preferred_period: Optional[str] = None,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    feature_flag_service.require_feature(db, tenant, "waitlist")

    from app.models.customer import TenantCustomer
    tc = db.query(TenantCustomer).filter(
        TenantCustomer.tenant_id == tenant.id,
        TenantCustomer.customer_account_id == customer_account_id,
    ).first()

    entry = WaitlistEntry(
        tenant_id=tenant.id,
        customer_account_id=customer_account_id,
        tenant_customer_id=tc.id if tc else None,
        service_ids=[str(s) for s in service_ids] if service_ids else None,
        preferred_professional_id=preferred_professional_id,
        preferred_period=preferred_period,
        status="waiting",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@waitlist_router.get("")
def list_waitlist(
    status: Optional[str] = "waiting",
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    feature_flag_service.require_feature(db, tenant, "waitlist")
    q = db.query(WaitlistEntry).filter(WaitlistEntry.tenant_id == tenant.id)
    if status:
        q = q.filter(WaitlistEntry.status == status)
    return q.order_by(WaitlistEntry.created_at).all()


@waitlist_router.patch("/{entry_id}/status")
def update_waitlist_status(
    entry_id: uuid.UUID,
    status: str,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    feature_flag_service.require_feature(db, tenant, "waitlist")
    entry = db.query(WaitlistEntry).filter(
        WaitlistEntry.id == entry_id, WaitlistEntry.tenant_id == tenant.id
    ).first()
    if not entry:
        raise NotFoundError("WAITLIST_NOT_FOUND", "Entrada não encontrada.")
    entry.status = status
    db.commit()
    return {"message": "Status atualizado."}
