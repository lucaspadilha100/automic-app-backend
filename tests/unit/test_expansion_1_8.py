"""Unit tests for Expansion 1.8 — billing and invoices."""
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4
import os

import pytest
from pydantic import ValidationError

# Importing the full model graph ensures every relationship() target is present
# in SQLAlchemy's class registry before any mapper.configure runs. Without this,
# instantiating TenantInvoice (which triggers configure_mappers via the
# tenant relationship chain) would fail to resolve User → Professional → ...
# We mirror the exact import block from alembic/env.py.
from app.models.plan import Plan as _Plan  # noqa: F401
from app.models.tenant import (  # noqa: F401
    Tenant as _Tenant, TenantSubscription as _TenantSubscription,
    TenantLimitOverride as _TLO, TenantFeatureFlag as _TFF,
    TenantSettings as _TS, TenantTheme as _TT, ThemePreset as _TP,
    TenantBookingPolicy as _TBP, TenantPaymentSettings as _TPS,
)
from app.models.user import User as _User, PasswordResetToken as _PRT, UserInvite as _UI  # noqa: F401
from app.models.customer import (  # noqa: F401
    CustomerAccount as _CA, TenantCustomer as _TC, CustomerTag as _CT,
    CustomerTagLink as _CTL, CustomerNote as _CN,
)
from app.models.service import ServiceCategory as _SC, Service as _Service, ProfessionalService as _PS  # noqa: F401
from app.models.professional import Professional as _Professional, ProfessionalAvailability as _PA  # noqa: F401
from app.models.schedule import BusinessHour as _BH, BlockedTime as _BT  # noqa: F401
from app.models.appointment import (  # noqa: F401
    Appointment as _Appt, AppointmentService as _AS, AppointmentStatusHistory as _ASH,
    IdempotencyKey as _IK,
)
from app.models.payment import Payment as _Payment  # noqa: F401
from app.models.package import (  # noqa: F401
    Package as _Pkg, PackageService as _PkS, CustomerPackage as _CP, PackageSession as _PS2,
)
from app.models.procedure import ProcedureHistory as _PH  # noqa: F401
from app.models.event import CustomerEvent as _CE  # noqa: F401
from app.models.audit import AuditLog as _AuditLog  # noqa: F401
from app.models.notification import NotificationTemplate as _NT, NotificationLog as _NL  # noqa: F401
from app.models.webhook import WebhookEndpoint as _WE, WebhookDelivery as _WD  # noqa: F401
from app.models.media import MediaFile as _MF  # noqa: F401
from app.models.resource import Resource as _Res, ServiceResource as _SR, AppointmentResource as _AR  # noqa: F401
from app.models.waitlist import WaitlistEntry as _WLE  # noqa: F401
from app.models.unit import Unit as _Unit  # noqa: F401
from app.models.future import AppointmentReview as _ARv, Coupon as _Cp, AppointmentHold as _AH  # noqa: F401
from app.models.term import TenantTerm as _TTerm, CustomerTermAcceptance as _CTA  # noqa: F401
from app.models.procedure_photo import ProcedurePhoto as _PP  # noqa: F401
from app.models.commission import ProfessionalCommissionSetting as _PCS, CommissionRecord as _CR  # noqa: F401
from app.models.custom_form import CustomForm as _CF, CustomFormField as _CFF, CustomFormResponse as _CFR  # noqa: F401
from app.models.customer_lifecycle import TenantLifecycleSetting as _TLS  # noqa: F401
from app.models.automation import AutomationRule as _AR2  # noqa: F401
from app.models.whatsapp import TenantWhatsAppSettings as _TWS  # noqa: F401
from app.models.platform_settings import PlatformSettings as _PSet  # noqa: F401
from app.models.support_ticket import SupportTicket as _ST, SupportTicketMessage as _STM  # noqa: F401
from app.models.owner_notification import OwnerNotification as _ON  # noqa: F401
from app.models.platform_document import PlatformDocument as _PD  # noqa: F401
from app.models.tenant_invoice import TenantInvoice as _TI  # noqa: F401

from app.services.invoice_service import InvoiceService
from app.services.billing_provider import (
    MockBillingProvider, MercadoPagoBillingProvider,
    get_billing_provider, reset_billing_provider,
)
from app.models.tenant_invoice import InvoiceStatus
from app.schemas.tenant_invoice import (
    InvoicePaidUpdate, InvoiceCancelUpdate, InvoiceChargeRequest,
)
from app.core.exceptions import ConflictError, NotFoundError


# ── Billing provider ──────────────────────────────────────────────────────────

class TestBillingProvider:
    def setup_method(self):
        reset_billing_provider()

    def teardown_method(self):
        reset_billing_provider()
        os.environ.pop("BILLING_PROVIDER", None)
        os.environ.pop("MERCADOPAGO_ACCESS_TOKEN", None)

    def test_default_is_mock(self):
        p = get_billing_provider()
        assert isinstance(p, MockBillingProvider)

    def test_returns_singleton(self):
        a = get_billing_provider()
        b = get_billing_provider()
        assert a is b

    def test_mock_pix_returns_qr(self):
        p = MockBillingProvider()
        result = p.create_charge(
            invoice_id=uuid4(), amount=197.0, currency="BRL",
            method="pix", tenant_name="Studio X",
        )
        assert result.payment_method == "pix"
        assert result.payment_qr_code is not None
        assert result.expires_at is not None
        assert result.payment_provider == "mock"

    def test_mock_card_returns_link(self):
        p = MockBillingProvider()
        result = p.create_charge(
            invoice_id=uuid4(), amount=347.0, currency="BRL",
            method="credit_card", tenant_name="Studio Y",
        )
        assert result.payment_link is not None

    def test_mp_without_token_raises(self):
        p = MercadoPagoBillingProvider(access_token=None)
        with pytest.raises(RuntimeError, match="MERCADOPAGO_ACCESS_TOKEN"):
            p.create_charge(
                invoice_id=uuid4(), amount=100.0, currency="BRL",
                method="pix", tenant_name="X",
            )

    def test_mp_with_token_raises_not_implemented(self):
        # The skeleton intentionally raises NotImplementedError until we wire HTTP
        p = MercadoPagoBillingProvider(access_token="fake")
        with pytest.raises(NotImplementedError):
            p.create_charge(
                invoice_id=uuid4(), amount=100.0, currency="BRL",
                method="pix", tenant_name="X",
            )

    def test_env_switch_to_mp(self):
        os.environ["BILLING_PROVIDER"] = "mercadopago"
        os.environ["MERCADOPAGO_ACCESS_TOKEN"] = "fake"
        reset_billing_provider()
        p = get_billing_provider()
        assert isinstance(p, MercadoPagoBillingProvider)


# ── Invoice schemas ───────────────────────────────────────────────────────────

class TestInvoiceSchemas:
    def test_paid_requires_payment_method(self):
        with pytest.raises(ValidationError):
            InvoicePaidUpdate(payment_method="")

    def test_paid_defaults_provider_to_manual(self):
        m = InvoicePaidUpdate(payment_method="pix")
        assert m.payment_provider == "manual"

    def test_cancel_requires_reason(self):
        with pytest.raises(ValidationError):
            InvoiceCancelUpdate(reason="")

    def test_charge_defaults_to_pix(self):
        m = InvoiceChargeRequest()
        assert m.method == "pix"


# ── Invoice service: idempotent generation ────────────────────────────────────

class TestInvoiceGeneration:
    def setup_method(self):
        self.svc = InvoiceService()

    def test_skips_already_invoiced_tenant(self):
        """Re-running generation for the same period must skip already-issued tenants."""
        from app.models.tenant import Tenant, TenantSubscription
        from app.models.tenant_invoice import TenantInvoice

        tenant = MagicMock(id=uuid4(), name="X", deleted_at=None, status="active")

        db = MagicMock()
        # Tenant query returns 1 tenant
        tenant_q = MagicMock()
        tenant_q.filter.return_value.all.return_value = [tenant]

        # Existing invoice = MagicMock (truthy) → triggers skip
        invoice_filter_q = MagicMock()
        invoice_filter_q.first.return_value = MagicMock()  # exists
        invoice_q = MagicMock()
        invoice_q.filter.return_value = invoice_filter_q

        def query_side_effect(model):
            if model is Tenant:
                return tenant_q
            if model is TenantInvoice:
                return invoice_q
            return MagicMock()

        db.query.side_effect = query_side_effect

        result = self.svc.generate_monthly_invoices(
            db,
            period_start=date(2026, 5, 1),
            period_end=date(2026, 5, 31),
        )
        assert result["created_count"] == 0
        assert result["skipped_reasons"]["already_invoiced"] == 1

    def test_generates_invoice_for_active_tenant_with_active_sub(self):
        """Tenant active + sub active + no existing invoice → creates 1 invoice."""
        from app.models.tenant import Tenant, TenantSubscription
        from app.models.tenant_invoice import TenantInvoice
        from app.models.plan import Plan

        tenant = MagicMock(id=uuid4(), deleted_at=None, status="active")
        tenant.name = "X"  # `name` is special on MagicMock — must set as attribute
        sub = MagicMock(
            id=uuid4(), tenant_id=tenant.id, plan_id=uuid4(),
            status="active", trial_ends_at=None, custom_price_monthly=None,
        )
        plan = MagicMock(id=sub.plan_id, price_monthly=Decimal("197"))
        plan.name = "Pro"

        db = MagicMock()

        def query_side_effect(model):
            q = MagicMock()
            if model is Tenant:
                q.filter.return_value.all.return_value = [tenant]
            elif model is TenantInvoice:
                # No existing invoice for this period
                q.filter.return_value.first.return_value = None
            elif model is TenantSubscription:
                q.filter.return_value.order_by.return_value.first.return_value = sub
            elif model is Plan:
                q.filter.return_value.first.return_value = plan
            return q

        db.query.side_effect = query_side_effect

        result = self.svc.generate_monthly_invoices(
            db,
            period_start=date(2026, 5, 1),
            period_end=date(2026, 5, 31),
        )
        assert result["created_count"] == 1
        # Verify added invoice has correct snapshot price
        added_invoices = [
            c.args[0] for c in db.add.call_args_list
            if hasattr(c.args[0], "amount")
        ]
        assert len(added_invoices) == 1
        assert added_invoices[0].amount == Decimal("197")
        assert added_invoices[0].plan_name_snapshot == "Pro"

    def test_uses_custom_price_when_set(self):
        from app.models.tenant import Tenant, TenantSubscription
        from app.models.tenant_invoice import TenantInvoice
        from app.models.plan import Plan

        tenant = MagicMock(id=uuid4(), deleted_at=None, status="active")
        tenant.name = "X"
        sub = MagicMock(
            id=uuid4(), tenant_id=tenant.id, plan_id=uuid4(),
            status="active", trial_ends_at=None,
            custom_price_monthly=Decimal("120"),
        )
        plan = MagicMock(id=sub.plan_id, price_monthly=Decimal("197"))
        plan.name = "Pro"

        db = MagicMock()

        def query_side_effect(model):
            q = MagicMock()
            if model is Tenant:
                q.filter.return_value.all.return_value = [tenant]
            elif model is TenantInvoice:
                q.filter.return_value.first.return_value = None
            elif model is TenantSubscription:
                q.filter.return_value.order_by.return_value.first.return_value = sub
            elif model is Plan:
                q.filter.return_value.first.return_value = plan
            return q

        db.query.side_effect = query_side_effect

        result = self.svc.generate_monthly_invoices(
            db,
            period_start=date(2026, 5, 1),
            period_end=date(2026, 5, 31),
        )
        assert result["created_count"] == 1
        invoices = [
            c.args[0] for c in db.add.call_args_list
            if hasattr(c.args[0], "amount")
        ]
        assert invoices[0].amount == Decimal("120")  # custom, not 197


# ── Mark paid / cancel ────────────────────────────────────────────────────────

class TestInvoiceMutations:
    def setup_method(self):
        self.svc = InvoiceService()

    def _stub_get_invoice(self, status):
        inv = MagicMock(id=uuid4(), status=status, paid_at=None)
        return inv

    def test_mark_paid_idempotent(self):
        inv = self._stub_get_invoice(InvoiceStatus.paid)
        db = MagicMock()
        with patch.object(self.svc, "get_invoice", return_value=inv):
            result = self.svc.mark_paid(
                db, inv.id, payment_method="pix", payment_provider="manual",
            )
        # No commit needed — already paid
        assert result is inv

    def test_mark_paid_rejects_cancelled(self):
        inv = self._stub_get_invoice(InvoiceStatus.cancelled)
        db = MagicMock()
        with patch.object(self.svc, "get_invoice", return_value=inv):
            with pytest.raises(ConflictError):
                self.svc.mark_paid(db, inv.id, payment_method="pix")

    def test_mark_paid_pending_succeeds(self):
        inv = self._stub_get_invoice(InvoiceStatus.pending)
        db = MagicMock()
        # Make the post-payment notification a no-op so we don't depend on db lookups
        with patch.object(self.svc, "get_invoice", return_value=inv), \
             patch.object(self.svc, "_notify_invoice_paid"):
            result = self.svc.mark_paid(
                db, inv.id, payment_method="pix",
                payment_reference="abc123",
            )
        assert result.status == InvoiceStatus.paid
        assert result.paid_at is not None
        assert result.payment_method == "pix"
        assert result.payment_reference == "abc123"
        # At least one commit (the mark-paid itself)
        assert db.commit.call_count >= 1

    def test_cancel_rejects_paid(self):
        inv = self._stub_get_invoice(InvoiceStatus.paid)
        db = MagicMock()
        with patch.object(self.svc, "get_invoice", return_value=inv):
            with pytest.raises(ConflictError):
                self.svc.cancel_invoice(db, inv.id, "test")

    def test_cancel_overdue_succeeds(self):
        inv = self._stub_get_invoice(InvoiceStatus.overdue)
        db = MagicMock()
        with patch.object(self.svc, "get_invoice", return_value=inv):
            result = self.svc.cancel_invoice(db, inv.id, "negociado")
        assert result.status == InvoiceStatus.cancelled
        assert result.cancellation_reason == "negociado"


# ── mark_overdue ──────────────────────────────────────────────────────────────

class TestMarkOverdue:
    def setup_method(self):
        self.svc = InvoiceService()

    def test_no_pending_returns_zero(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        result = self.svc.mark_overdue(db)
        assert result["marked_overdue_count"] == 0
        db.commit.assert_not_called()

    def test_pending_past_due_become_overdue(self):
        db = MagicMock()
        inv1 = MagicMock(status=InvoiceStatus.pending)
        inv2 = MagicMock(status=InvoiceStatus.pending)
        db.query.return_value.filter.return_value.all.return_value = [inv1, inv2]
        result = self.svc.mark_overdue(db)
        assert result["marked_overdue_count"] == 2
        assert inv1.status == InvoiceStatus.overdue
        assert inv2.status == InvoiceStatus.overdue
        db.commit.assert_called_once()
