"""
TenantInvoice — recurring billing invoices issued by AUTOMIC to its tenants.

Each tenant gets one invoice per billing period (typically monthly), priced
at their effective_price_monthly (custom_price if set, plan price otherwise).

Status flow:
    pending -> paid             (master ou webhook do provider de pagamento)
    pending -> overdue          (cron `mark_overdue` quando due_date < hoje)
    overdue -> paid             (atraso pago)
    overdue -> suspended_tenant (cron de suspensão por >7 dias)
    overdue -> cancelled_tenant (cron de cancelamento por >30 dias)
    pending|overdue -> cancelled (master cancela fatura — não cobra)
"""
import enum
from sqlalchemy import (
    Column, String, Numeric, DateTime, Date, Text, ForeignKey, Index,
    Enum as SAEnum, CheckConstraint, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base_model import UUIDPrimaryKey, TimestampMixin
from db.base import Base


class InvoiceStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    overdue = "overdue"
    cancelled = "cancelled"


class TenantInvoice(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "tenant_invoices"

    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    subscription_id = Column(
        UUID(as_uuid=True), ForeignKey("tenant_subscriptions.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # Period the invoice covers
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)

    # Pricing snapshot at issue time (so future plan changes don't affect old invoices)
    plan_name_snapshot = Column(String(100), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(8), nullable=False, default="BRL")

    status = Column(
        SAEnum(InvoiceStatus, name="invoice_status", create_type=False),
        nullable=False, default=InvoiceStatus.pending, index=True,
    )

    # Payment metadata (filled when paid or charge is created)
    payment_method = Column(String(50), nullable=True)        # 'pix', 'credit_card', 'manual'
    payment_provider = Column(String(50), nullable=True)      # 'mock', 'mercadopago', 'manual'
    payment_reference = Column(String(255), nullable=True)    # external txn id
    payment_qr_code = Column(Text, nullable=True)             # for Pix QR
    payment_link = Column(String(500), nullable=True)         # checkout URL
    paid_at = Column(DateTime(timezone=True), nullable=True)

    # Cancellation / notes
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Free-form provider payload
    provider_payload = Column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "period_start", "period_end",
            name="uq_tenant_invoices_tenant_period",
        ),
        CheckConstraint("amount >= 0", name="ck_tenant_invoices_amount_non_negative"),
        Index("ix_tenant_invoices_status_due_date", "status", "due_date"),
    )
