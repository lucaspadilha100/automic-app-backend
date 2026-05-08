"""
Manual payment + billing-mode endpoints for the AUTOMIC owner.

These cover the "I negotiated payment via Pix outside the app" workflow
without forcing automatic billing onto every tenant. Use case:

  1. New tenant opens trial → status=trial, billing_mode=manual
  2. Trial ends → you negotiate plan + price by WhatsApp
  3. Cliente paga PIX direto pra você
  4. You hit POST /master/tenants/{id}/manual-payment with the amount
     → marks current pending invoice as paid, reactivates tenant if suspended,
     emits owner notification.
  5. Want to switch to automatic later? PATCH /billing-mode → 'automatic'
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import require_super_admin, get_tenant_by_id_for_master
from app.core.exceptions import NotFoundError, ConflictError, ValidationError
from app.models.user import User
from app.models.tenant import Tenant, TenantSubscription
from app.models.tenant_invoice import TenantInvoice, InvoiceStatus
from app.services.audit_service import audit_service
from app.services.owner_notification_service import owner_notification_service
from app.services.invoice_service import invoice_service

router = APIRouter(prefix="/master/tenants", tags=["Tenants — Billing manual"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ManualPaymentRequest(BaseModel):
    amount: Decimal = Field(..., ge=0, description="Valor recebido em BRL")
    payment_method: str = Field("pix", min_length=1, max_length=50)
    payment_reference: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = Field(None, max_length=1000)
    invoice_id: Optional[uuid.UUID] = Field(
        None,
        description=(
            "Optional: specific invoice to mark paid. "
            "If omitted, the oldest pending/overdue invoice is used."
        ),
    )
    reactivate_if_suspended: bool = True


class ManualPaymentResponse(BaseModel):
    invoice_id: uuid.UUID
    invoice_status: str
    amount: Decimal
    paid_at: datetime
    tenant_status_before: str
    tenant_status_after: str
    reactivated: bool
    model_config = ConfigDict(from_attributes=True)


class BillingModeUpdate(BaseModel):
    billing_mode: str = Field(..., description="manual | automatic | free")


class BillingModeResponse(BaseModel):
    tenant_id: uuid.UUID
    billing_mode: str
    subscription_id: uuid.UUID


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/{tenant_id}/manual-payment", response_model=ManualPaymentResponse)
def register_manual_payment(
    payload: ManualPaymentRequest,
    tenant: Tenant = Depends(get_tenant_by_id_for_master),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """
    Register a manual payment received outside the app (Pix, transferência, etc).

    Flow:
      1. Find target invoice (specific id, or oldest pending/overdue)
      2. Mark it as paid (idempotent)
      3. Reactivate tenant if currently suspended (and reactivate_if_suspended=True)
      4. Emit owner notification + audit log
    """
    # Find the invoice to mark paid
    if payload.invoice_id:
        invoice = (
            db.query(TenantInvoice)
            .filter(
                TenantInvoice.id == payload.invoice_id,
                TenantInvoice.tenant_id == tenant.id,
            )
            .first()
        )
        if not invoice:
            raise NotFoundError(
                code="INVOICE_NOT_FOUND",
                message="Fatura não encontrada para este tenant.",
            )
    else:
        invoice = (
            db.query(TenantInvoice)
            .filter(
                TenantInvoice.tenant_id == tenant.id,
                TenantInvoice.status.in_((InvoiceStatus.pending, InvoiceStatus.overdue)),
            )
            .order_by(TenantInvoice.due_date.asc())
            .first()
        )
        if not invoice:
            raise NotFoundError(
                code="NO_PENDING_INVOICE",
                message=(
                    "Tenant não possui fatura pendente ou em atraso. "
                    "Gere uma fatura via /master/jobs/generate-monthly-invoices "
                    "ou passe invoice_id explicitamente."
                ),
            )

    if invoice.status == InvoiceStatus.cancelled:
        raise ConflictError(
            code="INVOICE_CANCELLED",
            message="Fatura está cancelada e não pode receber pagamento.",
        )

    # Mark paid (idempotent — service handles already-paid case)
    invoice = invoice_service.mark_paid(
        db=db, invoice_id=invoice.id,
        payment_method=payload.payment_method,
        payment_provider="manual",
        payment_reference=payload.payment_reference,
        notes=payload.notes,
    )

    # Optionally reactivate the tenant
    tenant_status_before = tenant.status
    reactivated = False
    if payload.reactivate_if_suspended and tenant.status == "suspended":
        tenant.status = "active"
        sub = (
            db.query(TenantSubscription)
            .filter(TenantSubscription.tenant_id == tenant.id)
            .order_by(TenantSubscription.created_at.desc())
            .first()
        )
        if sub and sub.status in ("past_due", "suspended"):
            sub.status = "active"
            db.add(sub)
        db.add(tenant)
        reactivated = True
        try:
            owner_notification_service.emit_tenant_status_change(
                db, tenant.id, tenant.name, "suspended", "active",
            )
        except Exception:
            pass
        db.commit()
        db.refresh(tenant)

    # Audit
    try:
        audit_service.log(
            db, "manual_payment_registered", "tenant", tenant.id,
            user_id=current_user.id,
            new_values={
                "invoice_id": str(invoice.id),
                "amount": str(payload.amount),
                "method": payload.payment_method,
                "reactivated": reactivated,
            },
        )
        db.commit()
    except Exception:
        pass

    return ManualPaymentResponse(
        invoice_id=invoice.id,
        invoice_status=invoice.status.value,
        amount=invoice.amount,
        paid_at=invoice.paid_at or datetime.now(timezone.utc),
        tenant_status_before=tenant_status_before,
        tenant_status_after=tenant.status,
        reactivated=reactivated,
    )


@router.patch("/{tenant_id}/billing-mode", response_model=BillingModeResponse)
def update_billing_mode(
    payload: BillingModeUpdate,
    tenant: Tenant = Depends(get_tenant_by_id_for_master),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """
    Switch the tenant's billing_mode between 'manual', 'automatic', 'free'.

    Use 'automatic' once you have Mercado Pago wired and the tenant agreed
    to recurring charges. Use 'free' for VIPs / testers / founder pricing.
    Default for new tenants is 'manual' until you change it.
    """
    if payload.billing_mode not in ("manual", "automatic", "free"):
        raise ValidationError(
            message="billing_mode deve ser 'manual', 'automatic' ou 'free'.",
        )

    sub = (
        db.query(TenantSubscription)
        .filter(TenantSubscription.tenant_id == tenant.id)
        .order_by(TenantSubscription.created_at.desc())
        .first()
    )
    if not sub:
        raise NotFoundError(
            code="NO_SUBSCRIPTION",
            message="Tenant não possui subscription.",
        )

    old_mode = sub.billing_mode
    sub.billing_mode = payload.billing_mode
    db.add(sub)

    try:
        audit_service.log(
            db, "billing_mode_changed", "tenant_subscription", sub.id,
            user_id=current_user.id,
            old_values={"billing_mode": old_mode},
            new_values={"billing_mode": payload.billing_mode},
        )
    except Exception:
        pass

    db.commit()
    db.refresh(sub)
    return BillingModeResponse(
        tenant_id=tenant.id,
        billing_mode=sub.billing_mode,
        subscription_id=sub.id,
    )


@router.get("/{tenant_id}/billing-mode", response_model=BillingModeResponse)
def get_billing_mode(
    tenant: Tenant = Depends(get_tenant_by_id_for_master),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    sub = (
        db.query(TenantSubscription)
        .filter(TenantSubscription.tenant_id == tenant.id)
        .order_by(TenantSubscription.created_at.desc())
        .first()
    )
    if not sub:
        raise NotFoundError(
            code="NO_SUBSCRIPTION",
            message="Tenant não possui subscription.",
        )
    return BillingModeResponse(
        tenant_id=tenant.id,
        billing_mode=sub.billing_mode,
        subscription_id=sub.id,
    )
