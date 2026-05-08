"""
Service for tenant subscription invoices.

Functions:
  - generate_monthly_invoices(period_start, period_end) — bulk-create one
    invoice per active/trial tenant for the upcoming month. Idempotent thanks
    to the (tenant_id, period_start, period_end) unique constraint.
  - mark_paid / mark_overdue / cancel_invoice
  - create_charge — wires through BillingProvider to fill QR / link
  - enforce_billing — cron that suspends/cancels delinquent tenants and
    reactivates after payment
"""
from __future__ import annotations
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
import uuid
import logging

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.tenant import Tenant, TenantSubscription, TenantSettings
from app.models.tenant_invoice import TenantInvoice, InvoiceStatus
from app.models.plan import Plan
from app.services.effective_plan_service import effective_plan_service
from app.services.owner_notification_service import owner_notification_service
from app.services.billing_provider import get_billing_provider
from app.core.exceptions import NotFoundError, ConflictError, ValidationError

logger = logging.getLogger(__name__)

# Configurable thresholds — kept centralized so we can move them to env later.
SUSPEND_AFTER_OVERDUE_DAYS = 7
CANCEL_AFTER_OVERDUE_DAYS = 30
DUE_DAYS_AFTER_PERIOD_START = 5  # invoice issued at period_start, due 5 days later


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return _utcnow().date()


class InvoiceService:
    # ── Generation ──────────────────────────────────────────────────────────
    def generate_monthly_invoices(
        self,
        db: Session,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Issue one invoice per active/trial tenant for the given monthly period.

        Defaults to "current month" if no dates given.

        Idempotent — re-runs skip tenants that already have an invoice for
        that exact period.
        """
        if period_start is None:
            today = _today()
            period_start = date(today.year, today.month, 1)
        if period_end is None:
            # last day of period_start month
            if period_start.month == 12:
                period_end = date(period_start.year, 12, 31)
            else:
                first_next = date(period_start.year, period_start.month + 1, 1)
                period_end = first_next - timedelta(days=1)

        due_date = period_start + timedelta(days=DUE_DAYS_AFTER_PERIOD_START)

        created = 0
        skipped_reasons: Dict[str, int] = {}

        tenants = (
            db.query(Tenant)
            .filter(
                Tenant.deleted_at.is_(None),
                Tenant.status.in_(("active", "trial")),
            )
            .all()
        )

        for tenant in tenants:
            # Skip if this tenant already has an invoice for this exact period
            existing = (
                db.query(TenantInvoice)
                .filter(
                    TenantInvoice.tenant_id == tenant.id,
                    TenantInvoice.period_start == period_start,
                    TenantInvoice.period_end == period_end,
                )
                .first()
            )
            if existing:
                skipped_reasons["already_invoiced"] = skipped_reasons.get("already_invoiced", 0) + 1
                continue

            sub = (
                db.query(TenantSubscription)
                .filter(TenantSubscription.tenant_id == tenant.id)
                .order_by(TenantSubscription.created_at.desc())
                .first()
            )
            if not sub:
                skipped_reasons["no_subscription"] = skipped_reasons.get("no_subscription", 0) + 1
                continue

            # Skip 'free' mode tenants entirely — no invoice for them
            if sub.billing_mode == "free":
                skipped_reasons["free_mode"] = skipped_reasons.get("free_mode", 0) + 1
                continue

            # Don't bill if subscription was cancelled or in trial that hasn't ended yet
            # (we charge at the END of the trial, not during)
            if sub.status == "cancelled":
                skipped_reasons["subscription_cancelled"] = skipped_reasons.get("subscription_cancelled", 0) + 1
                continue
            if sub.status == "trial" and sub.trial_ends_at and sub.trial_ends_at.date() > period_end:
                skipped_reasons["still_in_trial"] = skipped_reasons.get("still_in_trial", 0) + 1
                continue

            # Compute effective price
            plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()
            if not plan:
                skipped_reasons["no_plan"] = skipped_reasons.get("no_plan", 0) + 1
                continue
            effective_price = (
                Decimal(str(sub.custom_price_monthly))
                if sub.custom_price_monthly is not None
                else Decimal(str(plan.price_monthly or 0))
            )

            invoice = TenantInvoice(
                tenant_id=tenant.id,
                subscription_id=sub.id,
                period_start=period_start,
                period_end=period_end,
                due_date=due_date,
                plan_name_snapshot=plan.name,
                amount=effective_price,
                currency="BRL",
                status=InvoiceStatus.pending,
            )
            db.add(invoice)
            created += 1

        if created:
            db.commit()
        return {
            "period_start": period_start,
            "period_end": period_end,
            "created_count": created,
            "skipped_count": sum(skipped_reasons.values()),
            "skipped_reasons": skipped_reasons,
        }

    # ── Lookups ─────────────────────────────────────────────────────────────
    def get_invoice(self, db: Session, invoice_id: uuid.UUID) -> TenantInvoice:
        inv = db.query(TenantInvoice).filter(TenantInvoice.id == invoice_id).first()
        if not inv:
            raise NotFoundError(code="INVOICE_NOT_FOUND", message="Fatura não encontrada.")
        return inv

    def list_invoices(
        self,
        db: Session,
        tenant_id: Optional[uuid.UUID] = None,
        status: Optional[InvoiceStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TenantInvoice]:
        q = db.query(TenantInvoice)
        if tenant_id:
            q = q.filter(TenantInvoice.tenant_id == tenant_id)
        if status:
            q = q.filter(TenantInvoice.status == status)
        return (
            q.order_by(TenantInvoice.due_date.desc(), TenantInvoice.created_at.desc())
            .offset(offset).limit(limit).all()
        )

    # ── Mutations ───────────────────────────────────────────────────────────
    def mark_paid(
        self,
        db: Session,
        invoice_id: uuid.UUID,
        payment_method: str,
        payment_provider: str = "manual",
        payment_reference: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> TenantInvoice:
        inv = self.get_invoice(db, invoice_id)
        if inv.status == InvoiceStatus.paid:
            return inv  # idempotent
        if inv.status == InvoiceStatus.cancelled:
            raise ConflictError(
                code="INVOICE_CANCELLED",
                message="Fatura cancelada não pode ser marcada como paga.",
            )
        inv.status = InvoiceStatus.paid
        inv.paid_at = _utcnow()
        inv.payment_method = payment_method
        inv.payment_provider = payment_provider
        if payment_reference:
            inv.payment_reference = payment_reference
        if notes:
            inv.notes = notes
        db.add(inv)
        db.commit()
        db.refresh(inv)

        # Best-effort: email receipt to the tenant owner
        try:
            self._notify_invoice_paid(db, inv)
        except Exception as e:
            logger.warning("invoice_paid notification failed: %s", e)

        return inv

    def _notify_invoice_paid(self, db: Session, invoice: TenantInvoice) -> None:
        """Send 'invoice_paid' receipt email to the tenant owner. Best effort."""
        from app.models.user import User
        from app.services.notification_service import notification_service
        owner = (
            db.query(User)
            .filter(
                User.tenant_id == invoice.tenant_id,
                User.role == "tenant_owner",
                User.deleted_at.is_(None),
            )
            .first()
        )
        if not owner or not owner.email:
            return
        notification_service.send_generic(
            db, tenant_id=invoice.tenant_id, channel="email",
            event_type="invoice_paid", to=owner.email,
            context={
                "owner_name": owner.name,
                "invoice_amount": str(invoice.amount),
                "invoice_period": f"{invoice.period_start} a {invoice.period_end}",
            },
        )

    def cancel_invoice(
        self,
        db: Session, invoice_id: uuid.UUID, reason: str,
    ) -> TenantInvoice:
        inv = self.get_invoice(db, invoice_id)
        if inv.status == InvoiceStatus.paid:
            raise ConflictError(
                code="INVOICE_PAID", message="Fatura já paga não pode ser cancelada.",
            )
        inv.status = InvoiceStatus.cancelled
        inv.cancelled_at = _utcnow()
        inv.cancellation_reason = reason
        db.add(inv)
        db.commit()
        db.refresh(inv)
        return inv

    def mark_overdue(self, db: Session) -> Dict[str, Any]:
        """Sweep pending invoices past their due_date and flip them to overdue."""
        today = _today()
        rows = (
            db.query(TenantInvoice)
            .filter(
                TenantInvoice.status == InvoiceStatus.pending,
                TenantInvoice.due_date < today,
            )
            .all()
        )
        count = 0
        for inv in rows:
            inv.status = InvoiceStatus.overdue
            db.add(inv)
            count += 1
        if count:
            db.commit()
        return {"checked_at": _utcnow(), "marked_overdue_count": count}

    # ── Charge initiation ───────────────────────────────────────────────────
    def create_charge(
        self,
        db: Session, invoice_id: uuid.UUID, method: str,
    ) -> Dict[str, Any]:
        inv = self.get_invoice(db, invoice_id)
        if inv.status not in (InvoiceStatus.pending, InvoiceStatus.overdue):
            raise ConflictError(
                code="INVOICE_NOT_CHARGEABLE",
                message=f"Fatura no status '{inv.status.value}' não pode ser cobrada.",
            )
        tenant = db.query(Tenant).filter(Tenant.id == inv.tenant_id).first()
        provider = get_billing_provider()
        result = provider.create_charge(
            invoice_id=inv.id,
            amount=float(inv.amount),
            currency=inv.currency,
            method=method,
            tenant_name=tenant.name if tenant else "Tenant",
        )
        inv.payment_method = result.payment_method
        inv.payment_provider = result.payment_provider
        if result.payment_qr_code:
            inv.payment_qr_code = result.payment_qr_code
        if result.payment_link:
            inv.payment_link = result.payment_link
        if result.provider_reference:
            inv.payment_reference = result.provider_reference
        if result.raw_payload:
            inv.provider_payload = result.raw_payload
        db.add(inv)
        db.commit()
        db.refresh(inv)
        return {
            "invoice_id": inv.id,
            "payment_method": inv.payment_method,
            "payment_provider": inv.payment_provider,
            "payment_qr_code": inv.payment_qr_code,
            "payment_link": inv.payment_link,
            "amount": inv.amount,
            "currency": inv.currency,
            "expires_at": result.expires_at,
        }

    # ── Enforcement (cron) ──────────────────────────────────────────────────
    def enforce_billing(self, db: Session) -> Dict[str, Any]:
        """
        Apply billing rules to delinquent / paid tenants.

        ⚠️ Respects subscription.billing_mode:
          - 'manual': skipped entirely (you control status manually)
          - 'free':   skipped entirely (no charges expected)
          - 'automatic': full enforcement applies

        Behaviors when billing_mode == 'automatic':
        - tenant active+trial with overdue invoice >= SUSPEND_AFTER_OVERDUE_DAYS
              -> tenant.status = 'suspended', subscription.status = 'past_due'
        - tenant active+trial+suspended with overdue invoice >= CANCEL_AFTER_OVERDUE_DAYS
              -> tenant.status = 'cancelled', subscription.status = 'cancelled'
        - tenant suspended whose invoices are all paid/cancelled
              -> tenant.status = 'active', subscription.status = 'active'

        Idempotent. Emits OwnerNotification for every transition.
        """
        today = _today()
        suspended: List[uuid.UUID] = []
        cancelled: List[uuid.UUID] = []
        reactivated: List[uuid.UUID] = []
        skipped_manual = 0
        skipped_free = 0

        # Find all tenants with overdue invoices, group by tenant
        overdue_rows = (
            db.query(
                TenantInvoice.tenant_id,
                func.min(TenantInvoice.due_date).label("oldest_due_date"),
            )
            .filter(TenantInvoice.status == InvoiceStatus.overdue)
            .group_by(TenantInvoice.tenant_id)
            .all()
        )

        for tenant_id, oldest_due in overdue_rows:
            tenant = (
                db.query(Tenant)
                .filter(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
                .first()
            )
            if not tenant or tenant.status == "cancelled":
                continue
            sub = (
                db.query(TenantSubscription)
                .filter(TenantSubscription.tenant_id == tenant_id)
                .order_by(TenantSubscription.created_at.desc())
                .first()
            )
            # Skip non-automatic — you control these manually
            mode = (sub.billing_mode if sub else "manual")
            if mode == "manual":
                skipped_manual += 1
                continue
            if mode == "free":
                skipped_free += 1
                continue

            days_overdue = (today - oldest_due).days

            if days_overdue >= CANCEL_AFTER_OVERDUE_DAYS:
                old_status = tenant.status
                tenant.status = "cancelled"
                if sub:
                    sub.status = "cancelled"
                db.add(tenant)
                if sub:
                    db.add(sub)
                cancelled.append(tenant.id)
                try:
                    owner_notification_service.emit_tenant_status_change(
                        db, tenant.id, tenant.name, old_status, "cancelled",
                    )
                except Exception as e:
                    logger.warning("notif failure: %s", e)
            elif days_overdue >= SUSPEND_AFTER_OVERDUE_DAYS and tenant.status != "suspended":
                old_status = tenant.status
                tenant.status = "suspended"
                if sub:
                    sub.status = "past_due"
                db.add(tenant)
                if sub:
                    db.add(sub)
                suspended.append(tenant.id)
                try:
                    owner_notification_service.emit_tenant_status_change(
                        db, tenant.id, tenant.name, old_status, "suspended",
                    )
                except Exception as e:
                    logger.warning("notif failure: %s", e)

        # Reactivation: tenants currently suspended whose overdue invoices
        # have all been resolved (paid or cancelled). Only for 'automatic' mode —
        # 'manual' tenants are reactivated by you via the manual-payment endpoint.
        suspended_tenants = (
            db.query(Tenant)
            .filter(Tenant.status == "suspended", Tenant.deleted_at.is_(None))
            .all()
        )
        for tenant in suspended_tenants:
            still_overdue = (
                db.query(TenantInvoice)
                .filter(
                    TenantInvoice.tenant_id == tenant.id,
                    TenantInvoice.status == InvoiceStatus.overdue,
                )
                .count()
            )
            if still_overdue == 0:
                sub = (
                    db.query(TenantSubscription)
                    .filter(TenantSubscription.tenant_id == tenant.id)
                    .order_by(TenantSubscription.created_at.desc())
                    .first()
                )
                # Only auto-reactivate when in automatic mode
                if not sub or sub.billing_mode != "automatic":
                    continue
                old_status = tenant.status
                tenant.status = "active"
                sub.status = "active"
                db.add(sub)
                db.add(tenant)
                reactivated.append(tenant.id)
                try:
                    owner_notification_service.emit_tenant_status_change(
                        db, tenant.id, tenant.name, old_status, "active",
                    )
                except Exception as e:
                    logger.warning("notif failure: %s", e)

        if suspended or cancelled or reactivated:
            db.commit()

        return {
            "checked_at": _utcnow(),
            "suspended_count": len(suspended),
            "cancelled_count": len(cancelled),
            "reactivated_count": len(reactivated),
            "skipped_manual": skipped_manual,
            "skipped_free": skipped_free,
            "tenants_suspended": suspended,
            "tenants_cancelled": cancelled,
            "tenants_reactivated": reactivated,
        }


invoice_service = InvoiceService()
