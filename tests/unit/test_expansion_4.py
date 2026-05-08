"""Unit tests for Expansion 4 — billing modes + manual payment."""
from datetime import datetime, timezone, date
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

# Register full mapper graph
from tests.unit.test_expansion_1_8 import _Plan, _Tenant, _User  # noqa: F401

from app.services.invoice_service import InvoiceService
from app.models.tenant_invoice import InvoiceStatus
from app.api.routes.master_billing_manual import (
    ManualPaymentRequest, BillingModeUpdate,
)


# ── Schema validation ────────────────────────────────────────────────────────

class TestManualPaymentRequestSchema:
    def test_minimal_valid_payload(self):
        m = ManualPaymentRequest(amount=Decimal("197"))
        assert m.amount == Decimal("197")
        assert m.payment_method == "pix"  # default
        assert m.reactivate_if_suspended is True

    def test_negative_amount_rejected(self):
        with pytest.raises(PydanticValidationError):
            ManualPaymentRequest(amount=Decimal("-5"))

    def test_zero_amount_accepted(self):
        # Zero is OK for free-tier comp invoices
        m = ManualPaymentRequest(amount=Decimal("0"))
        assert m.amount == Decimal("0")

    def test_full_payload(self):
        inv_id = uuid4()
        m = ManualPaymentRequest(
            amount=Decimal("297"),
            payment_method="transferencia",
            payment_reference="TX-998877",
            notes="Cliente fundador",
            invoice_id=inv_id,
            reactivate_if_suspended=False,
        )
        assert m.payment_method == "transferencia"
        assert m.invoice_id == inv_id
        assert m.reactivate_if_suspended is False


class TestBillingModeUpdateSchema:
    def test_accepts_valid_modes(self):
        for mode in ("manual", "automatic", "free"):
            m = BillingModeUpdate(billing_mode=mode)
            assert m.billing_mode == mode

    # Note: validation of allowed values is enforced in the route handler
    # (raises ValidationError), not in the Pydantic schema, to give a custom
    # error code. So Pydantic alone won't reject "garbage" values here.


# ── enforce_billing respects billing_mode ─────────────────────────────────────

class TestEnforceBillingRespectsBillingMode:
    def setup_method(self):
        self.svc = InvoiceService()

    def _make_db(self, tenant, sub):
        """Build a DB mock that returns 1 overdue invoice for `tenant`,
        and serves `tenant` and `sub` by id when asked."""
        from app.models.tenant import Tenant, TenantSubscription
        from app.models.tenant_invoice import TenantInvoice
        from datetime import timedelta as _td

        db = MagicMock()
        # 10 days overdue → triggers suspension (>=7) but not cancellation (<30)
        oldest_due = date.today() - _td(days=10)

        def query_side_effect(model):
            q = MagicMock()
            if model is TenantInvoice:
                # The grouped overdue query
                q.filter.return_value.group_by.return_value.all.return_value = [
                    (tenant.id, oldest_due),
                ]
                # The "still_overdue" check used in reactivation
                q.filter.return_value.count.return_value = 1
            elif model is Tenant:
                q.filter.return_value.first.return_value = tenant
                # Suspended-tenants list (reactivation pass)
                q.filter.return_value.all.return_value = []
            elif model is TenantSubscription:
                q.filter.return_value.order_by.return_value.first.return_value = sub
            else:
                q.filter.return_value.first.return_value = None
            # The grouped query for overdue rows
            q.filter.return_value.group_by.return_value.all.return_value = (
                q.filter.return_value.group_by.return_value.all.return_value
                if hasattr(q.filter.return_value, "group_by")
                else []
            )
            return q

        # Override the first .query() to return the grouped query result
        # directly for the TenantInvoice path, since the service does
        # db.query(TenantInvoice.tenant_id, func.min(...))
        original_query = db.query
        def query_router(*args, **kwargs):
            # If first arg is a model class, use the side_effect above
            if args and hasattr(args[0], "__tablename__"):
                return query_side_effect(args[0])
            # Otherwise it's the grouped query (TenantInvoice.tenant_id, func.min)
            grouped = MagicMock()
            grouped.filter.return_value.group_by.return_value.all.return_value = [
                (tenant.id, oldest_due),
            ]
            return grouped

        db.query = MagicMock(side_effect=query_router)
        return db

    def test_manual_mode_skipped(self):
        """A 'manual' billing_mode tenant with overdue invoice must NOT be suspended."""
        tenant = MagicMock(id=uuid4(), status="active", deleted_at=None)
        tenant.name = "Manual Co"
        sub = MagicMock(billing_mode="manual", status="active")
        db = self._make_db(tenant, sub)

        with patch("app.services.invoice_service.owner_notification_service"):
            result = self.svc.enforce_billing(db)

        # Tenant status must remain unchanged
        assert tenant.status == "active"
        assert result["suspended_count"] == 0
        assert result["skipped_manual"] >= 1

    def test_free_mode_skipped(self):
        tenant = MagicMock(id=uuid4(), status="active", deleted_at=None)
        tenant.name = "Free Co"
        sub = MagicMock(billing_mode="free", status="active")
        db = self._make_db(tenant, sub)

        with patch("app.services.invoice_service.owner_notification_service"):
            result = self.svc.enforce_billing(db)

        assert tenant.status == "active"
        assert result["skipped_free"] >= 1
        assert result["suspended_count"] == 0

    def test_automatic_mode_suspends(self):
        """An 'automatic' tenant with 8+ days overdue MUST be suspended."""
        tenant = MagicMock(id=uuid4(), status="active", deleted_at=None)
        tenant.name = "Auto Co"
        sub = MagicMock(billing_mode="automatic", status="active")
        db = self._make_db(tenant, sub)

        with patch("app.services.invoice_service.owner_notification_service"):
            result = self.svc.enforce_billing(db)

        # Should have suspended (oldest_due was Apr 1, today >> 7 days)
        assert tenant.status == "suspended"
        assert result["suspended_count"] == 1


# ── generate_monthly_invoices skips free tenants ──────────────────────────────

class TestGenerateInvoicesSkipsFree:
    def setup_method(self):
        self.svc = InvoiceService()

    def test_free_mode_skipped(self):
        from app.models.tenant import Tenant, TenantSubscription
        from app.models.tenant_invoice import TenantInvoice
        from app.models.plan import Plan

        tenant = MagicMock(id=uuid4(), deleted_at=None, status="active")
        tenant.name = "Free Co"
        sub = MagicMock(
            id=uuid4(), tenant_id=tenant.id, plan_id=uuid4(),
            status="active", trial_ends_at=None, custom_price_monthly=None,
            billing_mode="free",
        )

        db = MagicMock()
        def query_side_effect(model):
            q = MagicMock()
            if model is Tenant:
                q.filter.return_value.all.return_value = [tenant]
            elif model is TenantInvoice:
                q.filter.return_value.first.return_value = None
            elif model is TenantSubscription:
                q.filter.return_value.order_by.return_value.first.return_value = sub
            return q
        db.query.side_effect = query_side_effect

        result = self.svc.generate_monthly_invoices(
            db, period_start=date(2026, 5, 1), period_end=date(2026, 5, 31),
        )
        assert result["created_count"] == 0
        assert result["skipped_reasons"].get("free_mode") == 1


# ── Summary (Expansion 4 surface) ─────────────────────────────────────────────

class TestExpansion4Surface:
    def test_billing_enforcement_response_has_skipped_fields(self):
        """Make sure the schema surfaces skipped_manual/skipped_free."""
        from app.schemas.tenant_invoice import BillingEnforcementResponse
        m = BillingEnforcementResponse(
            checked_at=datetime.now(timezone.utc),
            suspended_count=0, cancelled_count=0, reactivated_count=0,
            tenants_suspended=[], tenants_cancelled=[], tenants_reactivated=[],
        )
        # Defaults
        assert m.skipped_manual == 0
        assert m.skipped_free == 0
