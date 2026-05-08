from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
import uuid

from app.models.term import TermType


class TenantTermCreate(BaseModel):
    title: str
    content: str
    term_type: TermType
    version: str = "1.0"
    is_active: bool = True


class TenantTermUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    term_type: Optional[TermType] = None
    version: Optional[str] = None
    is_active: Optional[bool] = None


class TenantTermStatusUpdate(BaseModel):
    is_active: bool


class TenantTermResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    content: str
    term_type: TermType
    version: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerTermAcceptanceResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    customer_account_id: uuid.UUID
    tenant_customer_id: Optional[uuid.UUID]
    term_id: uuid.UUID
    accepted_at: datetime
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerTermAcceptResponse(BaseModel):
    accepted: bool
    acceptance_id: uuid.UUID
    term_id: uuid.UUID
    term_type: TermType
    version: str
    accepted_at: datetime
