from decimal import Decimal
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from datetime import datetime
import uuid

from app.models.commission import CommissionType, CommissionStatus


class CommissionSettingCreate(BaseModel):
    professional_id: uuid.UUID
    commission_type: CommissionType
    commission_value: Decimal = Decimal("0")
    is_active: bool = True

    @field_validator("commission_value")
    @classmethod
    def value_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("commission_value não pode ser negativo.")
        return v

    @field_validator("commission_value")
    @classmethod
    def percentage_range(cls, v: Decimal, info) -> Decimal:
        data = info.data
        if data.get("commission_type") == CommissionType.percentage and v > 100:
            raise ValueError("Percentual não pode ultrapassar 100.")
        return v


class CommissionSettingUpdate(BaseModel):
    commission_type: Optional[CommissionType] = None
    commission_value: Optional[Decimal] = None
    is_active: Optional[bool] = None

    @field_validator("commission_value")
    @classmethod
    def value_non_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("commission_value não pode ser negativo.")
        return v


class CommissionSettingStatusUpdate(BaseModel):
    is_active: bool


class CommissionSettingResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    professional_id: uuid.UUID
    commission_type: CommissionType
    commission_value: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommissionRecordResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    appointment_id: uuid.UUID
    professional_id: uuid.UUID
    base_amount: Decimal
    commission_type: CommissionType
    commission_value: Decimal
    commission_amount: Decimal
    status: CommissionStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
