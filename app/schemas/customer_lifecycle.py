from decimal import Decimal
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Dict, List, Optional
from datetime import datetime
import uuid

LIFECYCLE_STATUSES = {"new", "active", "recurring", "inactive", "at_risk", "vip"}


class TenantLifecycleSettingsResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    inactive_after_days: int
    at_risk_after_days: int
    recurring_min_appointments: int
    vip_min_appointments: int
    vip_min_total_spent: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TenantLifecycleSettingsUpdate(BaseModel):
    inactive_after_days: Optional[int] = None
    at_risk_after_days: Optional[int] = None
    recurring_min_appointments: Optional[int] = None
    vip_min_appointments: Optional[int] = None
    vip_min_total_spent: Optional[Decimal] = None

    @field_validator("inactive_after_days", "at_risk_after_days",
                     "recurring_min_appointments", "vip_min_appointments")
    @classmethod
    def non_negative_int(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Valor não pode ser negativo.")
        return v

    @field_validator("vip_min_total_spent")
    @classmethod
    def non_negative_decimal(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Valor não pode ser negativo.")
        return v


class CustomerLifecycleResponse(BaseModel):
    tenant_customer_id: uuid.UUID
    customer_account_id: Optional[uuid.UUID]
    lifecycle_status: str
    last_appointment_at: Optional[datetime]
    next_appointment_at: Optional[datetime]
    total_spent: Decimal
    appointments_count: int
    no_show_count: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerLifecycleSummaryResponse(BaseModel):
    new: int = 0
    active: int = 0
    recurring: int = 0
    inactive: int = 0
    at_risk: int = 0
    vip: int = 0
    total: int = 0


class CustomerLifecycleCustomerListItem(BaseModel):
    tenant_customer_id: uuid.UUID
    customer_account_id: Optional[uuid.UUID]
    lifecycle_status: str
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    customer_since: Optional[datetime] = None
    last_appointment_at: Optional[datetime]
    next_appointment_at: Optional[datetime]
    total_spent: Decimal
    appointments_count: int
    no_show_count: int

    model_config = ConfigDict(from_attributes=True)


class CustomerLifecycleRecalculateResponse(BaseModel):
    tenant_customer_id: uuid.UUID
    previous_status: str
    current_status: str
    changed: bool
