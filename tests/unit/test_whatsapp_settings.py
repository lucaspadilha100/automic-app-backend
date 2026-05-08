"""Unit tests for the WhatsApp/n8n Integration Settings module."""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.main import app
from app.models.whatsapp import TenantWhatsAppSettings, WhatsAppStatus
from app.services.whatsapp_settings_service import WhatsAppSettingsService
from app.schemas.whatsapp import TenantWhatsAppSettingsUpdate, TenantWhatsAppStatusUpdate
from app.core.exceptions import FeatureDisabledError


# ── Model field tests ─────────────────────────────────────────────────────────

def test_tenant_whatsapp_settings_model_fields():
    assert TenantWhatsAppSettings.__tablename__ == "tenant_whatsapp_settings"
    for f in ("id", "tenant_id", "enabled", "provider", "connection_type",
              "webhook_url", "instance_id", "status", "last_connected_at",
              "created_at", "updated_at"):
        assert hasattr(TenantWhatsAppSettings, f), f"Missing field: {f}"


def test_whatsapp_status_enum_values():
    assert WhatsAppStatus.disconnected == "disconnected"
    assert WhatsAppStatus.connected == "connected"
    assert WhatsAppStatus.waiting_qr == "waiting_qr"
    assert WhatsAppStatus.error == "error"


# ── Route registration ────────────────────────────────────────────────────────

def test_whatsapp_routes_registered():
    routes = {(r.path, m) for r in app.routes if hasattr(r, "methods") for m in r.methods}
    expected = {
        ("/api/v1/admin/integrations/whatsapp", "GET"),
        ("/api/v1/admin/integrations/whatsapp", "PUT"),
        ("/api/v1/admin/integrations/whatsapp/status", "GET"),
        ("/api/v1/admin/integrations/whatsapp/status", "PATCH"),
    }
    missing = expected - routes
    assert not missing, f"Missing routes: {missing}"


# ── Schema validation tests ───────────────────────────────────────────────────

def test_schema_rejects_invalid_webhook_url():
    with pytest.raises(Exception):
        TenantWhatsAppSettingsUpdate(webhook_url="not-a-url")


def test_schema_accepts_valid_webhook_url():
    s = TenantWhatsAppSettingsUpdate(webhook_url="https://n8n.example.com/webhook/abc")
    assert s.webhook_url == "https://n8n.example.com/webhook/abc"


def test_schema_accepts_none_webhook_url():
    s = TenantWhatsAppSettingsUpdate(webhook_url=None)
    assert s.webhook_url is None


def test_schema_rejects_invalid_provider():
    with pytest.raises(Exception):
        TenantWhatsAppSettingsUpdate(provider="made_up_provider")


def test_schema_accepts_valid_provider():
    s = TenantWhatsAppSettingsUpdate(provider="n8n")
    assert s.provider == "n8n"


def test_schema_rejects_invalid_status():
    with pytest.raises(Exception):
        TenantWhatsAppStatusUpdate(status="unknown_status")


def test_schema_accepts_valid_statuses():
    for status in ("disconnected", "connected", "waiting_qr", "error"):
        s = TenantWhatsAppStatusUpdate(status=status)
        assert s.status == status


# ── Feature flag tests ────────────────────────────────────────────────────────

def test_feature_disabled_raises_on_get_settings():
    svc = WhatsAppSettingsService()
    db = MagicMock()
    tenant = MagicMock()

    with patch("app.services.whatsapp_settings_service.feature_flag_service") as mock_ff:
        mock_ff.require_feature.side_effect = FeatureDisabledError("whatsapp_integration")
        with pytest.raises(FeatureDisabledError):
            svc.get_settings(db=db, tenant=tenant)


def test_feature_disabled_raises_on_upsert():
    svc = WhatsAppSettingsService()
    db = MagicMock()
    tenant = MagicMock()

    with patch("app.services.whatsapp_settings_service.feature_flag_service") as mock_ff:
        mock_ff.require_feature.side_effect = FeatureDisabledError("whatsapp_integration")
        with pytest.raises(FeatureDisabledError):
            svc.upsert_settings(db=db, tenant=tenant, data={})


# ── Service logic tests ───────────────────────────────────────────────────────

def _make_tenant(tid=None):
    t = MagicMock()
    t.id = tid or uuid.uuid4()
    return t


def _make_settings(tenant_id=None, status="disconnected", enabled=False):
    s = MagicMock(spec=TenantWhatsAppSettings)
    s.id = uuid.uuid4()
    s.tenant_id = tenant_id or uuid.uuid4()
    s.enabled = enabled
    s.provider = None
    s.connection_type = None
    s.webhook_url = None
    s.instance_id = None
    s.status = status
    s.last_connected_at = None
    return s


def test_get_settings_returns_existing():
    svc = WhatsAppSettingsService()
    db = MagicMock()
    tenant = _make_tenant()
    existing = _make_settings(tenant_id=tenant.id)

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = existing
    db.query.return_value = q

    with patch("app.services.whatsapp_settings_service.feature_flag_service"):
        result = svc.get_settings(db=db, tenant=tenant)

    assert result is existing
    db.add.assert_not_called()


def test_get_settings_creates_default_when_none():
    svc = WhatsAppSettingsService()
    db = MagicMock()
    tenant = _make_tenant()

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = None  # no existing record
    db.query.return_value = q
    db.add.return_value = None
    db.flush.return_value = None

    with patch("app.services.whatsapp_settings_service.feature_flag_service"):
        result = svc.get_settings(db=db, tenant=tenant)

    db.add.assert_called_once()
    added = db.add.call_args[0][0]
    assert isinstance(added, TenantWhatsAppSettings)
    assert added.enabled is False
    assert added.status == "disconnected"


def test_upsert_settings_updates_fields():
    svc = WhatsAppSettingsService()
    db = MagicMock()
    tenant = _make_tenant()
    existing = _make_settings(tenant_id=tenant.id)

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = existing
    db.query.return_value = q
    db.flush.return_value = None
    db.commit.return_value = None
    db.refresh.side_effect = lambda obj: None

    with patch("app.services.whatsapp_settings_service.feature_flag_service"), \
         patch("app.services.whatsapp_settings_service.audit_service") as mock_audit:

        svc.upsert_settings(
            db=db, tenant=tenant,
            data={"provider": "n8n", "connection_type": "webhook",
                  "webhook_url": "https://n8n.example.com/webhook/test"},
        )

        assert existing.provider == "n8n"
        assert existing.connection_type == "webhook"
        assert existing.webhook_url == "https://n8n.example.com/webhook/test"
        mock_audit.log.assert_called_once()
        assert mock_audit.log.call_args.kwargs.get("action") == "whatsapp_settings_updated"


def test_update_status_connected_sets_last_connected_at():
    svc = WhatsAppSettingsService()
    db = MagicMock()
    tenant = _make_tenant()
    existing = _make_settings(tenant_id=tenant.id, status="waiting_qr")

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = existing
    db.query.return_value = q
    db.flush.return_value = None
    db.commit.return_value = None
    db.refresh.side_effect = lambda obj: None

    with patch("app.services.whatsapp_settings_service.feature_flag_service"), \
         patch("app.services.whatsapp_settings_service.audit_service"):

        svc.update_status(db=db, tenant=tenant, status="connected")

    assert existing.status == "connected"
    assert existing.last_connected_at is not None


def test_update_status_error_does_not_set_last_connected_at():
    svc = WhatsAppSettingsService()
    db = MagicMock()
    tenant = _make_tenant()
    existing = _make_settings(tenant_id=tenant.id, status="connected")
    existing.last_connected_at = None

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = existing
    db.query.return_value = q
    db.flush.return_value = None
    db.commit.return_value = None
    db.refresh.side_effect = lambda obj: None

    with patch("app.services.whatsapp_settings_service.feature_flag_service"), \
         patch("app.services.whatsapp_settings_service.audit_service"):

        svc.update_status(db=db, tenant=tenant, status="error")

    assert existing.status == "error"
    assert existing.last_connected_at is None


def test_update_status_calls_audit_log():
    svc = WhatsAppSettingsService()
    db = MagicMock()
    tenant = _make_tenant()
    existing = _make_settings(tenant_id=tenant.id, status="disconnected")

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = existing
    db.query.return_value = q
    db.flush.return_value = None
    db.commit.return_value = None
    db.refresh.side_effect = lambda obj: None

    with patch("app.services.whatsapp_settings_service.feature_flag_service"), \
         patch("app.services.whatsapp_settings_service.audit_service") as mock_audit:

        svc.update_status(db=db, tenant=tenant, status="waiting_qr")

    mock_audit.log.assert_called_once()
    assert mock_audit.log.call_args.kwargs.get("action") == "whatsapp_status_updated"


# ── Tenant isolation ──────────────────────────────────────────────────────────

def test_ensure_default_settings_creates_for_correct_tenant():
    svc = WhatsAppSettingsService()
    db = MagicMock()
    tenant_id = uuid.uuid4()

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = None
    db.query.return_value = q
    db.add.return_value = None
    db.flush.return_value = None

    result = svc.ensure_default_settings(db=db, tenant_id=tenant_id)
    db.add.assert_called_once()
    added = db.add.call_args[0][0]
    assert added.tenant_id == tenant_id
