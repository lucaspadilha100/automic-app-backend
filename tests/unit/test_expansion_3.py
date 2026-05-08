"""Unit tests for Expansion 3 — real notifications."""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4
import os

import pytest

# Register full mapper graph
from tests.unit.test_expansion_1_8 import _Plan, _Tenant, _User  # noqa: F401

from app.services.notification_provider import (
    MockNotificationProvider, ResendEmailProvider, ZenviaSmsProvider,
    N8nWhatsAppProvider, CompositeNotificationProvider,
    get_notification_provider, reset_notification_provider,
    SendResult, _normalize_phone,
)
from app.services.notification_service import (
    NotificationService, DEFAULT_TEMPLATES,
)
from app.services.reminder_service import ReminderService


# ── Mock provider ─────────────────────────────────────────────────────────────

class TestMockProvider:
    def setup_method(self):
        reset_notification_provider()
        # Clear env so factory picks mock
        for k in ("RESEND_API_KEY", "ZENVIA_API_KEY", "N8N_WEBHOOK_URL"):
            os.environ.pop(k, None)

    def teardown_method(self):
        reset_notification_provider()

    def test_factory_default_is_mock(self):
        p = get_notification_provider()
        assert isinstance(p, MockNotificationProvider)

    def test_factory_returns_singleton(self):
        a = get_notification_provider()
        b = get_notification_provider()
        assert a is b

    def test_email_records_send(self):
        p = MockNotificationProvider()
        result = p.send_email("a@b.com", "Hi", "Body!")
        assert result.success is True
        assert result.provider == "mock"
        sent = p.sent
        assert len(sent) == 1
        assert sent[0].channel == "email"
        assert sent[0].to == "a@b.com"
        assert sent[0].subject == "Hi"

    def test_sms_records_send(self):
        p = MockNotificationProvider()
        p.send_sms("+5511999999999", "Test SMS")
        assert p.sent[0].channel == "sms"
        assert p.sent[0].body == "Test SMS"

    def test_whatsapp_records_send(self):
        p = MockNotificationProvider()
        p.send_whatsapp("+5511999999999", "Test WA")
        assert p.sent[0].channel == "whatsapp"

    def test_reset_clears_sent(self):
        p = MockNotificationProvider()
        p.send_email("a@b.com", "Hi", "Body")
        p.reset()
        assert p.sent == []


# ── Resend skeleton ───────────────────────────────────────────────────────────

class TestResendProvider:
    def setup_method(self):
        for k in ("RESEND_API_KEY", "RESEND_LIVE"):
            os.environ.pop(k, None)

    def test_no_api_key_raises(self):
        p = ResendEmailProvider(api_key=None)
        with pytest.raises(RuntimeError, match="RESEND_API_KEY"):
            p.send_email("a@b.com", "Hi", "Body")

    def test_skeleton_mode_returns_success_without_request(self):
        # API key set but RESEND_LIVE not set → skeleton mode
        p = ResendEmailProvider(api_key="fake_key")
        result = p.send_email("a@b.com", "Hi", "Body")
        assert result.success is True
        assert result.provider == "resend"
        assert result.provider_reference == "skeleton-no-send"
        assert result.raw_payload == {"skeleton": True}

    def test_does_not_send_sms(self):
        p = ResendEmailProvider(api_key="fake")
        with pytest.raises(NotImplementedError):
            p.send_sms("+551199", "Body")


# ── Zenvia skeleton ───────────────────────────────────────────────────────────

class TestZenviaProvider:
    def setup_method(self):
        for k in ("ZENVIA_API_KEY", "ZENVIA_LIVE"):
            os.environ.pop(k, None)

    def test_no_api_key_raises(self):
        p = ZenviaSmsProvider(api_key=None)
        with pytest.raises(RuntimeError, match="ZENVIA_API_KEY"):
            p.send_sms("+5511999", "Hi")

    def test_skeleton_mode_works(self):
        p = ZenviaSmsProvider(api_key="fake")
        result = p.send_sms("+5511999", "Hi")
        assert result.success is True
        assert result.provider == "zenvia"


# ── n8n skeleton ──────────────────────────────────────────────────────────────

class TestN8nProvider:
    def setup_method(self):
        for k in ("N8N_WEBHOOK_URL", "N8N_LIVE"):
            os.environ.pop(k, None)

    def test_no_webhook_raises(self):
        p = N8nWhatsAppProvider(webhook_url=None)
        with pytest.raises(RuntimeError, match="N8N_WEBHOOK_URL"):
            p.send_whatsapp("+5511999", "Hi")

    def test_skeleton_mode_works(self):
        p = N8nWhatsAppProvider(webhook_url="https://example.com/x")
        result = p.send_whatsapp("+5511999", "Hi")
        assert result.success is True
        assert result.provider == "n8n"


# ── Composite ─────────────────────────────────────────────────────────────────

class TestComposite:
    def test_routes_each_channel_independently(self):
        email_p = MagicMock()
        email_p.send_email.return_value = SendResult(success=True, provider="email-mock")
        sms_p = MagicMock()
        sms_p.send_sms.return_value = SendResult(success=True, provider="sms-mock")
        wa_p = MagicMock()
        wa_p.send_whatsapp.return_value = SendResult(success=True, provider="wa-mock")

        comp = CompositeNotificationProvider(email=email_p, sms=sms_p, whatsapp=wa_p)
        comp.send_email("a@b.com", "S", "B")
        comp.send_sms("+551199", "B")
        comp.send_whatsapp("+551199", "B")

        email_p.send_email.assert_called_once()
        sms_p.send_sms.assert_called_once()
        wa_p.send_whatsapp.assert_called_once()


# ── Phone normalization ───────────────────────────────────────────────────────

class TestPhoneNormalization:
    def test_strips_non_digits(self):
        assert _normalize_phone("(11) 99999-9999") == "11999999999"

    def test_keeps_leading_plus(self):
        assert _normalize_phone("+55 (11) 99999-9999") == "+5511999999999"

    def test_handles_empty(self):
        assert _normalize_phone("") == ""


# ── Service template rendering ────────────────────────────────────────────────

class TestNotificationServiceRendering:
    def setup_method(self):
        self.svc = NotificationService()

    def test_render_substitutes_vars(self):
        out = self.svc._render_template("Olá {{name}}!", {"name": "Maria"})
        assert out == "Olá Maria!"

    def test_render_missing_var_stays_unsubstituted(self):
        # Existing behavior: only context keys passed are replaced;
        # vars not in context remain literal
        out = self.svc._render_template("Olá {{name}}!", {})
        assert out == "Olá {{name}}!"

    def test_render_handles_none_value(self):
        out = self.svc._render_template("Olá {{name}}!", {"name": None})
        assert out == "Olá !"


# ── Default templates registry ────────────────────────────────────────────────

class TestDefaultTemplates:
    def test_has_24h_reminder(self):
        assert "appointment_reminder_24h" in DEFAULT_TEMPLATES
        assert "email" in DEFAULT_TEMPLATES["appointment_reminder_24h"]
        assert "whatsapp" in DEFAULT_TEMPLATES["appointment_reminder_24h"]

    def test_has_tenant_welcome(self):
        assert "tenant_welcome" in DEFAULT_TEMPLATES
        assert "email" in DEFAULT_TEMPLATES["tenant_welcome"]

    def test_has_invoice_events(self):
        assert "invoice_due_3d" in DEFAULT_TEMPLATES
        assert "invoice_overdue" in DEFAULT_TEMPLATES
        assert "invoice_paid" in DEFAULT_TEMPLATES


# ── Reminder service window ───────────────────────────────────────────────────

class TestReminderService:
    def setup_method(self):
        self.svc = ReminderService()

    def test_no_appointments_returns_zeros(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        result = self.svc.send_24h_reminders(db)
        assert result["appointments_in_window"] == 0
        assert result["sent_email"] == 0
        assert result["sent_whatsapp"] == 0

    def test_processes_appointment_with_phone_and_email(self):
        # Build a mock appointment with everything populated
        from app.models.appointment import Appointment
        customer = MagicMock(name="customer", phone="+5511999999999",
                             email="m@x.com", id=uuid4())
        customer.name = "Maria"
        prof = MagicMock()
        prof.name = "Dr. Joana"
        tenant = MagicMock(id=uuid4(), timezone="America/Sao_Paulo")
        tenant.name = "Studio X"
        tenant.public_name = None

        appt = MagicMock(spec=Appointment)
        appt.id = uuid4()
        appt.customer_account = customer
        appt.tenant = tenant
        appt.tenant_id = tenant.id
        appt.professional = prof
        appt.appointment_services = []
        appt.start_datetime = datetime.now(timezone.utc) + timedelta(hours=24)
        appt.status = "confirmed"

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [appt]

        with patch("app.services.reminder_service.notification_service") as svc_mock:
            svc_mock.send_generic.return_value = MagicMock(status="sent")
            result = self.svc.send_24h_reminders(db)

        # Both whatsapp and email were attempted (customer has both)
        assert svc_mock.send_generic.call_count == 2
        assert result["sent_whatsapp"] == 1
        assert result["sent_email"] == 1
        assert result["appointments_in_window"] == 1
