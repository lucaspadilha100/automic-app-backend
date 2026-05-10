from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
import uuid

from db.session import get_db
from app.core.dependencies import require_active_tenant, require_manager_or_above
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.models.tenant import Tenant
from app.models.supply import Supply, AppointmentSupplyUsage
from app.models.appointment import Appointment

router = APIRouter(tags=["Insumos"])


# ---- Schemas ----

class SupplyCreate(BaseModel):
    name: str
    unit: str = "un"
    cost_price: Optional[Decimal] = None
    track_stock: bool = False
    stock_quantity: Optional[Decimal] = None
    low_stock_threshold: Optional[Decimal] = None
    is_active: bool = True

class SupplyUpdate(BaseModel):
    name: Optional[str] = None
    unit: Optional[str] = None
    cost_price: Optional[Decimal] = None
    track_stock: Optional[bool] = None
    stock_quantity: Optional[Decimal] = None
    low_stock_threshold: Optional[Decimal] = None
    is_active: Optional[bool] = None

class SupplyResponse(BaseModel):
    id: uuid.UUID
    name: str
    unit: str
    cost_price: Optional[Decimal]
    track_stock: bool
    stock_quantity: Optional[Decimal]
    low_stock_threshold: Optional[Decimal]
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

class StockAdjust(BaseModel):
    adjustment: Decimal
    reason: Optional[str] = None

class SupplyUsageCreate(BaseModel):
    supply_id: uuid.UUID
    quantity_used: Decimal
    notes: Optional[str] = None

class SupplyUsageResponse(BaseModel):
    id: uuid.UUID
    supply_id: uuid.UUID
    quantity_used: Decimal
    notes: Optional[str]
    supply: Optional[SupplyResponse]
    model_config = ConfigDict(from_attributes=True)


# ---- Supply routes ----

@router.get("/supplies", response_model=List[SupplyResponse])
def list_supplies(
    is_active: Optional[bool] = None,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    q = db.query(Supply).filter(Supply.tenant_id == tenant.id)
    if is_active is not None:
        q = q.filter(Supply.is_active == is_active)
    return q.order_by(Supply.name).all()


@router.get("/supplies/{supply_id}", response_model=SupplyResponse)
def get_supply(
    supply_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    s = db.query(Supply).filter(Supply.id == supply_id, Supply.tenant_id == tenant.id).first()
    if not s:
        raise NotFoundError("SUPPLY_NOT_FOUND", "Insumo não encontrado.")
    return s


@router.post("/supplies", response_model=SupplyResponse)
def create_supply(
    payload: SupplyCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    s = Supply(tenant_id=tenant.id, **payload.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.put("/supplies/{supply_id}", response_model=SupplyResponse)
def update_supply(
    supply_id: uuid.UUID,
    payload: SupplyUpdate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    s = db.query(Supply).filter(Supply.id == supply_id, Supply.tenant_id == tenant.id).first()
    if not s:
        raise NotFoundError("SUPPLY_NOT_FOUND", "Insumo não encontrado.")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return s


@router.delete("/supplies/{supply_id}")
def delete_supply(
    supply_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    s = db.query(Supply).filter(Supply.id == supply_id, Supply.tenant_id == tenant.id).first()
    if not s:
        raise NotFoundError("SUPPLY_NOT_FOUND", "Insumo não encontrado.")
    s.is_active = False
    db.commit()
    return {"message": "Insumo desativado."}


@router.post("/supplies/{supply_id}/adjust-stock", response_model=SupplyResponse)
def adjust_stock(
    supply_id: uuid.UUID,
    payload: StockAdjust,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    s = db.query(Supply).filter(Supply.id == supply_id, Supply.tenant_id == tenant.id).first()
    if not s:
        raise NotFoundError("SUPPLY_NOT_FOUND", "Insumo não encontrado.")
    s.stock_quantity = (s.stock_quantity or Decimal("0")) + payload.adjustment
    db.commit()
    db.refresh(s)
    return s


# ---- Appointment supply usage ----

@router.get("/appointments/{appointment_id}/supply-usage", response_model=List[SupplyUsageResponse])
def get_appointment_supply_usage(
    appointment_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id, Appointment.tenant_id == tenant.id).first()
    if not appt:
        raise NotFoundError("APPOINTMENT_NOT_FOUND", "Agendamento não encontrado.")
    return db.query(AppointmentSupplyUsage).filter(AppointmentSupplyUsage.appointment_id == appointment_id).all()


@router.post("/appointments/{appointment_id}/supply-usage", response_model=SupplyUsageResponse)
def add_supply_usage(
    appointment_id: uuid.UUID,
    payload: SupplyUsageCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id, Appointment.tenant_id == tenant.id).first()
    if not appt:
        raise NotFoundError("APPOINTMENT_NOT_FOUND", "Agendamento não encontrado.")
    supply = db.query(Supply).filter(Supply.id == payload.supply_id, Supply.tenant_id == tenant.id).first()
    if not supply:
        raise NotFoundError("SUPPLY_NOT_FOUND", "Insumo não encontrado.")
    usage = AppointmentSupplyUsage(
        tenant_id=tenant.id,
        appointment_id=appointment_id,
        supply_id=payload.supply_id,
        quantity_used=payload.quantity_used,
        notes=payload.notes,
    )
    if supply.track_stock and supply.stock_quantity is not None:
        supply.stock_quantity -= payload.quantity_used
    db.add(usage)
    db.commit()
    db.refresh(usage)
    return usage


@router.delete("/appointments/{appointment_id}/supply-usage/{usage_id}")
def remove_supply_usage(
    appointment_id: uuid.UUID,
    usage_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    usage = db.query(AppointmentSupplyUsage).filter(
        AppointmentSupplyUsage.id == usage_id,
        AppointmentSupplyUsage.appointment_id == appointment_id,
        AppointmentSupplyUsage.tenant_id == tenant.id,
    ).first()
    if not usage:
        raise NotFoundError("USAGE_NOT_FOUND", "Uso não encontrado.")
    supply = db.query(Supply).filter(Supply.id == usage.supply_id).first()
    if supply and supply.track_stock and supply.stock_quantity is not None:
        supply.stock_quantity += usage.quantity_used
    db.delete(usage)
    db.commit()
    return {"message": "Uso removido."}
