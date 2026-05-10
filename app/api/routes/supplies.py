from typing import List, Optional
from decimal import Decimal
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import (
    get_current_user, require_active_tenant, require_manager_or_above,
    require_receptionist_or_above, require_feature,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.models.user import User
from app.models.tenant import Tenant
from app.models.supply import Supply, AppointmentSupplyUsage
from app.models.appointment import Appointment
from app.services.audit_service import audit_service


# ---- Schemas ----

class SupplyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    unit: str = "un"
    cost_price: Decimal = Decimal("0")
    track_stock: bool = False
    stock_quantity: Decimal = Decimal("0")
    low_stock_threshold: Decimal = Decimal("5")
    is_active: bool = True


class SupplyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    cost_price: Optional[Decimal] = None
    track_stock: Optional[bool] = None
    stock_quantity: Optional[Decimal] = None
    low_stock_threshold: Optional[Decimal] = None
    is_active: Optional[bool] = None


class SupplyResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: Optional[str]
    unit: str
    cost_price: Decimal
    track_stock: bool
    stock_quantity: Decimal
    low_stock_threshold: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StockAdjustPayload(BaseModel):
    adjustment: Decimal
    reason: str


class SupplyUsageCreate(BaseModel):
    supply_id: uuid.UUID
    quantity_used: Decimal
    notes: Optional[str] = None


class SupplyUsageResponse(BaseModel):
    id: uuid.UUID
    appointment_id: uuid.UUID
    supply_id: uuid.UUID
    tenant_id: uuid.UUID
    quantity_used: Decimal
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---- Routers ----

router = APIRouter(
    prefix="/supplies",
    tags=["Product Usage"],
    dependencies=[Depends(require_feature("product_usage"))],
)

usage_router = APIRouter(
    prefix="/appointments",
    tags=["Product Usage"],
    dependencies=[Depends(require_feature("product_usage"))],
)


# ---- Supplies ----

@router.get("", response_model=List[SupplyResponse])
def list_supplies(
    active_only: bool = True,
    skip: int = 0,
    limit: int = 100,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Supply).filter(Supply.tenant_id == tenant.id, Supply.deleted_at.is_(None))
    if active_only:
        q = q.filter(Supply.is_active == True)
    return q.offset(skip).limit(limit).all()


@router.post("", response_model=SupplyResponse, status_code=201)
def create_supply(
    payload: SupplyCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    supply = Supply(tenant_id=tenant.id, **payload.model_dump())
    db.add(supply)
    db.flush()
    audit_service.log(db, "supply_created", "supply", supply.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(supply)
    return supply


@router.get("/{supply_id}", response_model=SupplyResponse)
def get_supply(
    supply_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    supply = db.query(Supply).filter(
        Supply.id == supply_id, Supply.tenant_id == tenant.id, Supply.deleted_at.is_(None)
    ).first()
    if not supply:
        raise NotFoundError("SUPPLY_NOT_FOUND", "Insumo não encontrado.")
    return supply


@router.put("/{supply_id}", response_model=SupplyResponse)
def update_supply(
    supply_id: uuid.UUID,
    payload: SupplyUpdate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    supply = db.query(Supply).filter(
        Supply.id == supply_id, Supply.tenant_id == tenant.id, Supply.deleted_at.is_(None)
    ).first()
    if not supply:
        raise NotFoundError("SUPPLY_NOT_FOUND", "Insumo não encontrado.")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(supply, k, v)
    audit_service.log(db, "supply_updated", "supply", supply.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(supply)
    return supply


@router.delete("/{supply_id}")
def delete_supply(
    supply_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    supply = db.query(Supply).filter(
        Supply.id == supply_id, Supply.tenant_id == tenant.id, Supply.deleted_at.is_(None)
    ).first()
    if not supply:
        raise NotFoundError("SUPPLY_NOT_FOUND", "Insumo não encontrado.")
    supply.deleted_at = datetime.now(timezone.utc)
    supply.is_active = False
    audit_service.log(db, "supply_deleted", "supply", supply.id, tenant.id, current_user.id)
    db.commit()
    return {"message": "Insumo removido."}


@router.post("/{supply_id}/adjust-stock", response_model=SupplyResponse)
def adjust_stock(
    supply_id: uuid.UUID,
    payload: StockAdjustPayload,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    supply = db.query(Supply).filter(
        Supply.id == supply_id, Supply.tenant_id == tenant.id, Supply.deleted_at.is_(None)
    ).first()
    if not supply:
        raise NotFoundError("SUPPLY_NOT_FOUND", "Insumo não encontrado.")
    new_qty = Decimal(str(supply.stock_quantity)) + payload.adjustment
    if new_qty < 0:
        raise ValidationError("Estoque insuficiente para este ajuste.")
    supply.stock_quantity = new_qty
    audit_service.log(db, "supply_stock_adjusted", "supply", supply.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(supply)
    return supply


# ---- Supply Usage ----

@usage_router.get("/{appointment_id}/supply-usage", response_model=List[SupplyUsageResponse])
def list_supply_usage(
    appointment_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id, Appointment.tenant_id == tenant.id
    ).first()
    if not appointment:
        raise NotFoundError("APPOINTMENT_NOT_FOUND", "Agendamento não encontrado.")
    return (
        db.query(AppointmentSupplyUsage)
        .filter(AppointmentSupplyUsage.appointment_id == appointment_id)
        .all()
    )


@usage_router.post("/{appointment_id}/supply-usage", response_model=SupplyUsageResponse, status_code=201)
def add_supply_usage(
    appointment_id: uuid.UUID,
    payload: SupplyUsageCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id, Appointment.tenant_id == tenant.id
    ).first()
    if not appointment:
        raise NotFoundError("APPOINTMENT_NOT_FOUND", "Agendamento não encontrado.")
    supply = db.query(Supply).filter(
        Supply.id == payload.supply_id, Supply.tenant_id == tenant.id, Supply.deleted_at.is_(None)
    ).first()
    if not supply:
        raise NotFoundError("SUPPLY_NOT_FOUND", "Insumo não encontrado.")
    if supply.track_stock:
        remaining = Decimal(str(supply.stock_quantity)) - payload.quantity_used
        if remaining < 0:
            raise ValidationError(f"Estoque insuficiente para o insumo '{supply.name}'.")
        supply.stock_quantity = remaining
    usage = AppointmentSupplyUsage(
        appointment_id=appointment_id,
        supply_id=payload.supply_id,
        tenant_id=tenant.id,
        quantity_used=payload.quantity_used,
        notes=payload.notes,
    )
    db.add(usage)
    db.flush()
    audit_service.log(db, "supply_usage_added", "appointment_supply_usage", usage.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(usage)
    return usage


@usage_router.delete("/{appointment_id}/supply-usage/{usage_id}")
def remove_supply_usage(
    appointment_id: uuid.UUID,
    usage_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    usage = db.query(AppointmentSupplyUsage).filter(
        AppointmentSupplyUsage.id == usage_id,
        AppointmentSupplyUsage.appointment_id == appointment_id,
        AppointmentSupplyUsage.tenant_id == tenant.id,
    ).first()
    if not usage:
        raise NotFoundError("USAGE_NOT_FOUND", "Registro de uso não encontrado.")
    supply = db.query(Supply).filter(Supply.id == usage.supply_id).first()
    if supply and supply.track_stock:
        supply.stock_quantity = Decimal(str(supply.stock_quantity)) + Decimal(str(usage.quantity_used))
    db.delete(usage)
    audit_service.log(db, "supply_usage_removed", "appointment_supply_usage", usage_id, tenant.id, current_user.id)
    db.commit()
    return {"message": "Registro de uso removido."}
