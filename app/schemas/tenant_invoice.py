from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, Dict, Any, List
from datetime import date, datetime
from decimal import Decimal
import uuid

from app.models.tenant_invoice import InvoiceStatus


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    subscription_id: Optional[uuid.UUID]
    period_start: date
    period_end: date
    due_date: date
    plan_name_snapshot: Optional[str]
    amount: Decimal
    currency: str
    status: InvoiceStatus
    payment_method: Optional[str]
    payment_provider: Optional[str]
    payment_reference: Optional[str]
    payment_qr_code: Optional[str]
    payment_link: Optional[str]
    paid_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    cancellation_reason: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InvoicePaidUpdate(BaseModel):
    payment_method: str = Field(..., min_length=1, max_length=50)
    payment_provider: str = Field("manual", min_length=1, max_length=50)
    payment_reference: Optional[str] = None
    notes: Optional[str] = None


class InvoiceCancelUpdate(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class InvoiceChargeRequest(BaseModel):
    """Initiate a payment charge (mock or real provider)."""
    method: str = Field("pix", min_length=1, max_length=20)


class InvoiceChargeResponse(BaseModel):
    invoice_id: uuid.UUID
    payment_method: str
    payment_provider: str
    payment_qr_code: Optional[str]
    payment_link: Optional[str]
    amount: Decimal
    currency: str
    expires_at: Optional[datetime]


class GenerateInvoicesResponse(BaseModel):
    period_start: date
    period_end: date
    created_count: int
    skipped_count: int
    skipped_reasons: Dict[str, int]


class MarkOverdueResponse(BaseModel):
    checked_at: datetime
    marked_overdue_count: int


class BillingEnforcementResponse(BaseModel):
    checked_at: datetime
    suspended_count: int
    cancelled_count: int
    reactivated_count: int
    skipped_manual: int = 0
    skipped_free: int = 0
    tenants_suspended: List[uuid.UUID]
    tenants_cancelled: List[uuid.UUID]
    tenants_reactivated: List[uuid.UUID]
