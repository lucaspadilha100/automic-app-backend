from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, List
from datetime import datetime
import uuid


class ScheduleExceptionCreate(BaseModel):
    professional_id: Optional[uuid.UUID] = None
    unit_id: Optional[uuid.UUID] = None
    start_datetime: datetime
    end_datetime: datetime
    exception_type: str = Field(..., description="holiday | leave | closure")
    reason: Optional[str] = Field(None, max_length=500)

    @field_validator("exception_type")
    @classmethod
    def _validate_type(cls, v):
        if v not in ("holiday", "leave", "closure"):
            raise ValueError("exception_type deve ser 'holiday', 'leave' ou 'closure'")
        return v

    @field_validator("end_datetime")
    @classmethod
    def _end_after_start(cls, v, info):
        start = info.data.get("start_datetime")
        if start and v <= start:
            raise ValueError("end_datetime deve ser maior que start_datetime")
        return v


class ScheduleExceptionUpdate(BaseModel):
    professional_id: Optional[uuid.UUID] = None
    unit_id: Optional[uuid.UUID] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    exception_type: Optional[str] = None
    reason: Optional[str] = Field(None, max_length=500)


class ScheduleExceptionResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    professional_id: Optional[uuid.UUID]
    unit_id: Optional[uuid.UUID]
    start_datetime: datetime
    end_datetime: datetime
    exception_type: str
    reason: Optional[str]
    created_by_user_id: Optional[uuid.UUID]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BulkCancelRequest(BaseModel):
    professional_id: uuid.UUID
    start_datetime: datetime
    end_datetime: datetime
    reason: str = Field(..., min_length=1, max_length=500)
    notify_customers: bool = True

    @field_validator("end_datetime")
    @classmethod
    def _end_after_start(cls, v, info):
        start = info.data.get("start_datetime")
        if start and v <= start:
            raise ValueError("end_datetime deve ser maior que start_datetime")
        return v


class BulkCancelResponse(BaseModel):
    cancelled_count: int
    notified_count: int
    appointment_ids: List[uuid.UUID]
