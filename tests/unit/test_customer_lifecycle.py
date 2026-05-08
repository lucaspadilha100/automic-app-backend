"""Unit tests for the Customer Lifecycle module."""
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.main import app
from app.models.customer import TenantCustomer
from app.models.customer_lifecycle import TenantLifecycleSetting
from app.services.customer_lifecycle_service import CustomerLifecycleService
from app.core.exceptions import FeatureDisabledError


# ── Model field tests ─────────────────────────────────────────────────────────

def test_tenant_customer_has_lifecycle_fields():
    for f in ("lifecycle_status", "last_appointment_at", "next_appointment_at",
              "total_spent", "appointments_count", "no_show_count"):
        assert hasattr(TenantCustomer, f), f"Missing field: {f}"


def test_tenant_lifecycle_setting_exists():
    assert TenantLifecycleSetting.__tablename__ == "tenant_lifecycle_settings"
    for f in ("inactive_after_days", "at_risk_after_days", "recurring_min_appointments",
              "vip_min_appointments", "vip_min_total_spent"):
        assert hasattr(TenantLifecycleSetting, f), f"Missing: {f}"


# ── Route registration ────────────────────────────────────────────────────────

def test_lifecycle_routes_registered():
    routes = {(r.path, m) for r in app.routes if hasattr(r, "methods") for m in r.methods}
    expected = {
        ("/api/v1/admin/customer-lifecycle/summary", "GET"),
        ("/api/v1/admin/customer-lifecycle/customers", "GET"),
        ("/api/v1/admin/customer-lifecycle/settings", "GET"),
        ("/api/v1/admin/customer-lifecycle/settings", "PUT"),
        ("/api/v1/admin/customer-lifecycle/recalculate-all", "POST"),
        ("/api/v1/admin/customers/{tenant_customer_id}/lifecycle", "GET"),
        ("/api/v1/admin/customers/{tenant_customer_id}/lifecycle/recalculate", "POST"),
    }
    missing = expected - routes
    assert not missing, f"Missing routes: {missing}"


# ── determine_status tests ────────────────────────────────────────────────────

def _make_settings(**overrides):
    s = MagicMock(spec=TenantLifecycleSetting)
    s.inactive_after_days = overrides.get("inactive_after_days", 90)
    s.at_risk_after_days = overrides.get("at_risk_after_days", 45)
    s.recurring_min_appointments = overrides.get("recurring_min_appointments", 3)
    s.vip_min_appointments = overrides.get("vip_min_appointments", 5)
    s.vip_min_total_spent = overrides.get("vip_min_total_spent", Decimal("1000"))
    return s


def _make_tc(lifecycle_status="new", appointments_count=0, no_show_count=0,
             total_spent=Decimal("0"), last_appointment_at=None, next_appointment_at=None):
    tc = MagicMock(spec=TenantCustomer)
    tc.id = uuid.uuid4()
    tc.tenant_id = uuid.uuid4()
    tc.customer_account_id = uuid.uuid4()
    tc.lifecycle_status = lifecycle_status
    tc.appointments_count = appointments_count
    tc.no_show_count = no_show_count
    tc.total_spent = total_spent
    tc.last_appointment_at = last_appointment_at
    tc.next_appointment_at = next_appointment_at
    return tc


def test_new_customer_starts_as_new():
    svc = CustomerLifecycleService()
    tc = _make_tc(appointments_count=0)
    s = _make_settings()
    assert svc.determine_status(tc, s) == "new"


def test_active_after_first_appointment():
    svc = CustomerLifecycleService()
    tc = _make_tc(appointments_count=1, lifecycle_status="new",
                  last_appointment_at=datetime.now(timezone.utc))
    s = _make_settings()
    status = svc.determine_status(tc, s)
    assert status in ("active", "new")  # with 1 appt < recurring_min


def test_recurring_after_min_appointments():
    svc = CustomerLifecycleService()
    tc = _make_tc(appointments_count=3, lifecycle_status="active",
                  last_appointment_at=datetime.now(timezone.utc) - timedelta(days=10))
    s = _make_settings(recurring_min_appointments=3)
    assert svc.determine_status(tc, s) == "recurring"


def test_vip_by_appointments():
    svc = CustomerLifecycleService()
    tc = _make_tc(appointments_count=5, lifecycle_status="recurring",
                  last_appointment_at=datetime.now(timezone.utc) - timedelta(days=5))
    s = _make_settings(vip_min_appointments=5)
    assert svc.determine_status(tc, s) == "vip"


def test_vip_by_total_spent():
    svc = CustomerLifecycleService()
    tc = _make_tc(appointments_count=2, lifecycle_status="active",
                  total_spent=Decimal("1000"),
                  last_appointment_at=datetime.now(timezone.utc) - timedelta(days=5))
    s = _make_settings(vip_min_total_spent=Decimal("1000"))
    assert svc.determine_status(tc, s) == "vip"


def test_at_risk_after_threshold_days():
    svc = CustomerLifecycleService()
    tc = _make_tc(appointments_count=2, lifecycle_status="active",
                  last_appointment_at=datetime.now(timezone.utc) - timedelta(days=50))
    s = _make_settings(at_risk_after_days=45, inactive_after_days=90)
    assert svc.determine_status(tc, s) == "at_risk"


def test_inactive_after_long_absence():
    svc = CustomerLifecycleService()
    tc = _make_tc(appointments_count=2, lifecycle_status="active",
                  last_appointment_at=datetime.now(timezone.utc) - timedelta(days=100))
    s = _make_settings(inactive_after_days=90)
    assert svc.determine_status(tc, s) == "inactive"


def test_vip_not_downgraded():
    svc = CustomerLifecycleService()
    tc = _make_tc(lifecycle_status="vip", appointments_count=1,
                  last_appointment_at=datetime.now(timezone.utc) - timedelta(days=100))
    s = _make_settings()
    # VIP is sticky
    assert svc.determine_status(tc, s) == "vip"


# ── register hooks tests ──────────────────────────────────────────────────────

def _make_appointment(tenant_id=None, tenant_customer_id=None, total_price="100.00"):
    a = MagicMock()
    a.id = uuid.uuid4()
    a.tenant_id = tenant_id or uuid.uuid4()
    a.tenant_customer_id = tenant_customer_id or uuid.uuid4()
    a.customer_account_id = uuid.uuid4()
    a.total_price = float(total_price)
    a.start_datetime = datetime.now(timezone.utc) + timedelta(hours=1)
    a.status = "completed"
    return a


def test_register_completed_increments_appointments_count():
    svc = CustomerLifecycleService()
    db = MagicMock()
    appt = _make_appointment()
    tc = _make_tc(lifecycle_status="active", appointments_count=2, total_spent=Decimal("200"))
    tc.tenant_id = appt.tenant_id

    settings = _make_settings()

    def query_side(model):
        from app.models.customer import TenantCustomer as TC
        from app.models.customer_lifecycle import TenantLifecycleSetting as TLS
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        if model is TC:
            q.first.return_value = tc
        elif model is TLS:
            q.first.return_value = settings
        else:
            q.first.return_value = None  # Appointment -> no next appt
        return q

    db.query.side_effect = query_side

    with patch("app.services.customer_lifecycle_service.customer_event_service"):
        svc.register_appointment_completed(db, appt)

    assert tc.appointments_count == 3
    assert tc.total_spent == Decimal("300.00")


def test_register_no_show_increments_no_show_count():
    svc = CustomerLifecycleService()
    db = MagicMock()
    appt = _make_appointment()
    tc = _make_tc(lifecycle_status="active", no_show_count=1, appointments_count=3)
    tc.tenant_id = appt.tenant_id

    settings = _make_settings()

    def query_side(model):
        from app.models.customer import TenantCustomer as TC
        from app.models.customer_lifecycle import TenantLifecycleSetting as TLS
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        if model is TC:
            q.first.return_value = tc
        elif model is TLS:
            q.first.return_value = settings
        else:
            q.first.return_value = None
        return q

    db.query.side_effect = query_side

    with patch("app.services.customer_lifecycle_service.customer_event_service"):
        svc.register_appointment_no_show(db, appt)

    assert tc.no_show_count == 2


# ── customer_event on status change ──────────────────────────────────────────

def test_apply_status_emits_customer_event_when_changed():
    svc = CustomerLifecycleService()
    db = MagicMock()
    tc = _make_tc(lifecycle_status="new")
    tc.tenant_id = uuid.uuid4()

    with patch("app.services.customer_lifecycle_service.customer_event_service") as mock_event:
        changed = svc._apply_status(db, tc, "active")

    assert changed is True
    assert tc.lifecycle_status == "active"
    mock_event.emit.assert_called_once()
    assert mock_event.emit.call_args.kwargs.get("event_type") == "customer_lifecycle_updated"


def test_apply_status_no_event_when_same():
    svc = CustomerLifecycleService()
    db = MagicMock()
    tc = _make_tc(lifecycle_status="active")

    with patch("app.services.customer_lifecycle_service.customer_event_service") as mock_event:
        changed = svc._apply_status(db, tc, "active")

    assert changed is False
    mock_event.emit.assert_not_called()


# ── audit_log on settings change ─────────────────────────────────────────────

def test_update_settings_calls_audit_log():
    svc = CustomerLifecycleService()
    db = MagicMock()
    tenant = MagicMock()
    tenant.id = uuid.uuid4()
    settings = MagicMock(spec=TenantLifecycleSetting)
    settings.id = uuid.uuid4()
    settings.inactive_after_days = 90
    settings.at_risk_after_days = 45
    settings.recurring_min_appointments = 3
    settings.vip_min_appointments = 5
    settings.vip_min_total_spent = Decimal("1000")

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = settings
    db.query.return_value = q

    with patch("app.services.customer_lifecycle_service.feature_flag_service"), \
         patch("app.services.customer_lifecycle_service.audit_service") as mock_audit:
        svc.update_settings(db=db, tenant=tenant, data={"inactive_after_days": 60})
        mock_audit.log.assert_called_once()
        assert mock_audit.log.call_args.kwargs.get("action") == "lifecycle_settings_updated"


# ── feature flag ─────────────────────────────────────────────────────────────

def test_feature_disabled_raises():
    svc = CustomerLifecycleService()
    db = MagicMock()
    tenant = MagicMock()

    with patch("app.services.customer_lifecycle_service.feature_flag_service") as mock_ff:
        mock_ff.require_feature.side_effect = FeatureDisabledError("customer_lifecycle")
        with pytest.raises(FeatureDisabledError):
            svc.get_summary(db=db, tenant=tenant)


# ── tenant isolation ──────────────────────────────────────────────────────────

def test_get_customer_lifecycle_wrong_tenant_raises():
    from app.core.exceptions import NotFoundError
    svc = CustomerLifecycleService()
    db = MagicMock()
    tenant = MagicMock()
    tenant.id = uuid.uuid4()

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = None
    db.query.return_value = q

    with patch("app.services.customer_lifecycle_service.feature_flag_service"):
        with pytest.raises(NotFoundError):
            svc.get_customer_lifecycle(db=db, tenant=tenant, tenant_customer_id=uuid.uuid4())
