"""
Unit tests for the commercial layer:
  - Plan defaults
  - Manual feature override (true/false)
  - Limit override
  - Custom price → effective price → MRR
  - Effective-plan source ("plan" / "manual_override")
  - Audit-log emission for commercial changes
  - FEATURE_DISABLED gating on Expansion-1 admin routes
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.main import app
from app.models.plan import Plan
from app.models.tenant import (
    Tenant, TenantSubscription, TenantFeatureFlag, TenantLimitOverride,
)
from app.services.effective_plan_service import (
    effective_plan_service, EffectivePlanService, PLAN_FEATURE_MAP, LIMIT_KEYS,
)
from app.services.feature_flag_service import (
    feature_flag_service, PLAN_FEATURE_MAP as FF_PLAN_FEATURE_MAP,
)
from app.core.exceptions import FeatureDisabledError


# ── Plan model — every required feature column exists ────────────────────────

def test_plan_model_has_all_feature_columns():
    expected = {
        "allow_packages", "allow_custom_terms", "allow_before_after_photos",
        "allow_commissions", "allow_custom_forms", "allow_customer_lifecycle",
        "allow_automation_rules", "allow_whatsapp_integration",
        "allow_online_payment", "allow_advanced_reports", "allow_crm_integration",
        "allow_multi_unit", "allow_waitlist", "allow_physical_resources", "allow_webhooks",
    }
    for f in expected:
        assert hasattr(Plan, f), f"Plan is missing column: {f}"


def test_plan_model_has_limit_columns():
    for f in (
        "max_services", "max_professionals", "max_users",
        "max_appointments_per_month", "max_units", "max_packages",
    ):
        assert hasattr(Plan, f), f"Plan is missing limit column: {f}"


def test_plan_model_has_price_monthly():
    assert hasattr(Plan, "price_monthly")


# ── TenantSubscription — commercial overrides ────────────────────────────────

def test_subscription_has_commercial_fields():
    for f in ("custom_price_monthly", "custom_price_reason", "billing_notes", "contracted_at"):
        assert hasattr(TenantSubscription, f), f"TenantSubscription missing: {f}"


def test_subscription_table_has_non_negative_price_constraint():
    constraints = {c.name for c in TenantSubscription.__table_args__ if hasattr(c, "name")}
    # SQLAlchemy may prefix the name; both forms are acceptable.
    assert any(
        "custom_price_non_negative" in name
        for name in constraints
    ), f"Missing non-negative-price constraint in {constraints}"


# ── feature_flag_service mapping is complete ─────────────────────────────────

def test_feature_flag_map_includes_commissions():
    assert "allow_commissions" in FF_PLAN_FEATURE_MAP
    assert FF_PLAN_FEATURE_MAP["allow_commissions"] == "commissions"


def test_effective_plan_feature_map_matches_required_keys():
    required_keys = {
        "packages", "custom_terms", "before_after_photos", "commissions",
        "custom_forms", "customer_lifecycle", "automation_rules", "whatsapp_integration",
        "online_payment", "advanced_reports", "crm_integration", "multi_unit",
        "waitlist", "physical_resources", "webhooks",
    }
    assert set(PLAN_FEATURE_MAP.keys()) == required_keys


# ── effective_plan_service — feature resolution ──────────────────────────────

def _mock_plan(**flags) -> MagicMock:
    """Build a MagicMock with all PLAN_FEATURE_MAP attrs set to False unless overridden."""
    p = MagicMock(spec=Plan)
    p.id = uuid.uuid4()
    p.name = flags.pop("name", "Pro")
    p.price_monthly = flags.pop("price_monthly", Decimal("197.00"))
    p.is_active = True
    for plan_attr in PLAN_FEATURE_MAP.values():
        setattr(p, plan_attr, False)
    for k in LIMIT_KEYS:
        setattr(p, k, None)
    for k, v in flags.items():
        setattr(p, k, v)
    return p


def _mock_subscription(plan_id, custom_price=None) -> MagicMock:
    s = MagicMock(spec=TenantSubscription)
    s.id = uuid.uuid4()
    s.plan_id = plan_id
    s.status = "active"
    s.starts_at = datetime.now(timezone.utc)
    s.trial_ends_at = None
    s.ends_at = None
    s.contracted_at = None
    s.custom_price_monthly = custom_price
    s.custom_price_reason = None
    s.billing_notes = None
    s.created_at = datetime.now(timezone.utc)
    return s


class _FakeQuery:
    """Tiny query mock: returns first() = value when filter is called."""
    def __init__(self, value):
        self._value = value
    def filter(self, *a, **k): return self
    def order_by(self, *a, **k): return self
    def first(self): return self._value


def _make_db(*, sub=None, plan=None, flags=None, override=None):
    """Set up a MagicMock db.session.query() that routes by the queried model."""
    flags = flags or {}

    def query_router(model):
        if model is TenantSubscription:
            return _FakeQuery(sub)
        if model is Plan:
            return _FakeQuery(plan)
        if model is TenantLimitOverride:
            return _FakeQuery(override)
        if model is TenantFeatureFlag:
            # filter().first() → look up by feature_key from a dict
            class _Q:
                def __init__(self, d): self._d = d; self._key = None
                def filter(self, *args, **kwargs):
                    # crude: scan args for BinaryExpression with .right matching string
                    for a in args:
                        right = getattr(a, "right", None)
                        val = getattr(right, "value", None) if right is not None else None
                        if isinstance(val, str) and val in self._d:
                            self._key = val
                    return self
                def first(self):
                    return self._d.get(self._key) if self._key else None
            return _Q(flags)
        return _FakeQuery(None)

    db = MagicMock()
    db.query.side_effect = query_router
    return db


def test_feature_from_plan_when_no_override():
    plan = _mock_plan(allow_commissions=True)
    sub = _mock_subscription(plan.id)
    db = _make_db(sub=sub, plan=plan)
    tenant_id = uuid.uuid4()

    res = effective_plan_service.get_feature_source(db, tenant_id, "commissions")
    assert res == {"enabled": True, "source": "plan"}


def test_manual_override_true_unlocks_feature_when_plan_disables():
    plan = _mock_plan(allow_before_after_photos=False)
    sub = _mock_subscription(plan.id)
    flag = MagicMock(spec=TenantFeatureFlag)
    flag.enabled = True
    flag.feature_key = "before_after_photos"
    db = _make_db(sub=sub, plan=plan, flags={"before_after_photos": flag})
    tenant_id = uuid.uuid4()

    res = effective_plan_service.get_feature_source(db, tenant_id, "before_after_photos")
    assert res == {"enabled": True, "source": "manual_override"}


def test_manual_override_false_blocks_feature_when_plan_enables():
    plan = _mock_plan(allow_commissions=True)
    sub = _mock_subscription(plan.id)
    flag = MagicMock(spec=TenantFeatureFlag)
    flag.enabled = False
    flag.feature_key = "commissions"
    db = _make_db(sub=sub, plan=plan, flags={"commissions": flag})
    tenant_id = uuid.uuid4()

    res = effective_plan_service.get_feature_source(db, tenant_id, "commissions")
    assert res == {"enabled": False, "source": "manual_override"}


def test_unknown_feature_key_returns_none():
    db = _make_db()
    assert effective_plan_service.get_feature_source(db, uuid.uuid4(), "made_up") is None


# ── effective_plan_service — limits ──────────────────────────────────────────

def test_limit_from_plan_when_no_override():
    plan = _mock_plan(max_services=50)
    sub = _mock_subscription(plan.id)
    db = _make_db(sub=sub, plan=plan)
    res = effective_plan_service.get_limit_source(db, uuid.uuid4(), "max_services")
    assert res == {"value": 50, "source": "plan"}


def test_limit_from_manual_override():
    plan = _mock_plan(max_services=50)
    sub = _mock_subscription(plan.id)
    override = MagicMock(spec=TenantLimitOverride)
    for k in LIMIT_KEYS:
        setattr(override, k, None)
    override.max_services = 999
    override.notes = "Custom"
    db = _make_db(sub=sub, plan=plan, override=override)
    res = effective_plan_service.get_limit_source(db, uuid.uuid4(), "max_services")
    assert res == {"value": 999, "source": "manual_override"}


def test_unknown_limit_key_returns_none():
    db = _make_db()
    assert effective_plan_service.get_limit_source(db, uuid.uuid4(), "max_zzz") is None


# ── effective_plan_service — pricing / MRR contribution ──────────────────────

def test_effective_price_uses_plan_when_no_custom_price():
    plan = _mock_plan(price_monthly=Decimal("197.00"))
    sub = _mock_subscription(plan.id, custom_price=None)
    db = _make_db(sub=sub, plan=plan)
    res = effective_plan_service.get_effective_price(db, uuid.uuid4())
    assert res["effective_price_monthly"] == Decimal("197.00")
    assert res["source"] == "plan"
    assert res["custom_price_monthly"] is None


def test_effective_price_uses_custom_when_set():
    plan = _mock_plan(price_monthly=Decimal("197.00"))
    sub = _mock_subscription(plan.id, custom_price=Decimal("120.00"))
    db = _make_db(sub=sub, plan=plan)
    res = effective_plan_service.get_effective_price(db, uuid.uuid4())
    assert res["effective_price_monthly"] == Decimal("120.00")
    assert res["source"] == "manual_override"
    assert res["plan_price_monthly"] == Decimal("197.00")


def test_effective_price_zero_when_no_subscription():
    db = _make_db(sub=None, plan=None)
    res = effective_plan_service.get_effective_price(db, uuid.uuid4())
    assert res["effective_price_monthly"] == Decimal("0")
    assert res["source"] == "plan"


# ── effective_plan_service — full payload ────────────────────────────────────

def test_get_effective_plan_returns_full_payload():
    plan = _mock_plan(allow_packages=True, allow_commissions=True, max_services=100)
    sub = _mock_subscription(plan.id, custom_price=Decimal("120.00"))
    db = _make_db(sub=sub, plan=plan)

    tenant = MagicMock(spec=Tenant)
    tenant.id = uuid.uuid4()

    payload = effective_plan_service.get_effective_plan(db, tenant)
    assert payload["tenant_id"] == str(tenant.id)
    assert payload["plan"]["name"] == "Pro"
    assert payload["subscription"]["effective_price_monthly"] == 120.0
    assert payload["subscription"]["price_source"] == "manual_override"
    assert payload["features"]["packages"] == {"enabled": True, "source": "plan"}
    assert payload["features"]["commissions"] == {"enabled": True, "source": "plan"}
    assert payload["features"]["before_after_photos"] == {"enabled": False, "source": "plan"}
    assert payload["limits"]["max_services"] == {"value": 100, "source": "plan"}


# ── feature_flag_service.is_enabled honors override ──────────────────────────

def test_feature_flag_service_returns_plan_default_without_override():
    plan = _mock_plan(allow_commissions=True)
    sub = _mock_subscription(plan.id)
    db = _make_db(sub=sub, plan=plan)
    tenant = MagicMock(spec=Tenant)
    tenant.id = uuid.uuid4()
    assert feature_flag_service.is_enabled(db, tenant, "commissions") is True


def test_feature_flag_service_override_blocks_plan():
    plan = _mock_plan(allow_commissions=True)
    sub = _mock_subscription(plan.id)
    flag = MagicMock(spec=TenantFeatureFlag)
    flag.enabled = False
    db = _make_db(sub=sub, plan=plan, flags={"commissions": flag})
    tenant = MagicMock(spec=Tenant)
    tenant.id = uuid.uuid4()
    assert feature_flag_service.is_enabled(db, tenant, "commissions") is False


def test_feature_flag_service_override_unlocks_plan():
    plan = _mock_plan(allow_commissions=False)
    sub = _mock_subscription(plan.id)
    flag = MagicMock(spec=TenantFeatureFlag)
    flag.enabled = True
    db = _make_db(sub=sub, plan=plan, flags={"commissions": flag})
    tenant = MagicMock(spec=Tenant)
    tenant.id = uuid.uuid4()
    assert feature_flag_service.is_enabled(db, tenant, "commissions") is True


def test_feature_flag_service_require_feature_raises_when_disabled():
    plan = _mock_plan(allow_commissions=False)
    sub = _mock_subscription(plan.id)
    db = _make_db(sub=sub, plan=plan)
    tenant = MagicMock(spec=Tenant)
    tenant.id = uuid.uuid4()
    with pytest.raises(FeatureDisabledError):
        feature_flag_service.require_feature(db, tenant, "commissions")


# ── Schema-level validation ──────────────────────────────────────────────────

def test_subscription_update_rejects_negative_custom_price():
    from app.schemas.tenant import SubscriptionUpdate
    with pytest.raises(Exception):
        SubscriptionUpdate(plan_id=uuid.uuid4(), custom_price_monthly=-1)


def test_subscription_update_accepts_none_custom_price():
    from app.schemas.tenant import SubscriptionUpdate
    s = SubscriptionUpdate(plan_id=uuid.uuid4(), custom_price_monthly=None)
    assert s.custom_price_monthly is None


def test_subscription_update_accepts_zero_custom_price():
    from app.schemas.tenant import SubscriptionUpdate
    s = SubscriptionUpdate(plan_id=uuid.uuid4(), custom_price_monthly=0)
    assert s.custom_price_monthly == 0


def test_plan_create_includes_all_feature_flags():
    from app.schemas.tenant import PlanCreate
    fields = set(PlanCreate.model_fields.keys())
    for k in (
        "allow_commissions", "allow_custom_forms", "allow_customer_lifecycle",
        "allow_automation_rules", "allow_whatsapp_integration",
    ):
        assert k in fields, f"PlanCreate missing field {k}"


# ── Routes: registration ─────────────────────────────────────────────────────

def test_master_commercial_routes_registered():
    routes = {(r.path, m) for r in app.routes if hasattr(r, "methods") for m in r.methods}
    expected = {
        ("/api/v1/master/tenants/{tenant_id}/effective-plan", "GET"),
        ("/api/v1/master/tenants/{tenant_id}/subscription", "PUT"),
        ("/api/v1/master/tenants/{tenant_id}/features", "GET"),
        ("/api/v1/master/tenants/{tenant_id}/features", "PUT"),
        ("/api/v1/master/tenants/{tenant_id}/limit-overrides", "GET"),
        ("/api/v1/master/tenants/{tenant_id}/limit-overrides", "PUT"),
        ("/api/v1/master/metrics/mrr", "GET"),
    }
    missing = expected - routes
    assert not missing, f"Missing master routes: {missing}"


# ── Expansion-1 routes are now feature-gated ─────────────────────────────────

def _routes_in(prefix: str):
    return [
        r for r in app.routes
        if hasattr(r, "path") and r.path.startswith(prefix)
    ]


def test_admin_terms_router_feature_gated():
    """admin_terms must require the `custom_terms` feature at the router level."""
    from app.api.routes.admin_terms import router as r
    deps = [d.dependency for d in r.dependencies if hasattr(d, "dependency")]
    # The require_feature factory returns a closure, so we look for the marker name.
    found = any(getattr(fn, "__qualname__", "").startswith("require_feature") for fn in deps)
    assert found, "admin_terms router missing require_feature dependency"


def test_admin_procedure_photos_router_feature_gated():
    from app.api.routes.admin_procedure_photos import router as r
    deps = [d.dependency for d in r.dependencies if hasattr(d, "dependency")]
    found = any(getattr(fn, "__qualname__", "").startswith("require_feature") for fn in deps)
    assert found, "admin_procedure_photos router missing require_feature dependency"


def test_admin_commissions_router_feature_gated():
    from app.api.routes.admin_commissions import router as r
    deps = [d.dependency for d in r.dependencies if hasattr(d, "dependency")]
    found = any(getattr(fn, "__qualname__", "").startswith("require_feature") for fn in deps)
    assert found, "admin_commissions router missing require_feature dependency"


# ── Audit emission on commercial endpoint paths ──────────────────────────────

def test_update_subscription_emits_price_audit_when_price_changes():
    """Drives the master_tenants.update_subscription handler with a fake DB and
    verifies subscription_custom_price_updated is emitted exactly when price changes."""
    from app.api.routes import master_tenants as mt

    tenant = MagicMock(spec=Tenant)
    tenant.id = uuid.uuid4()
    user = MagicMock()
    user.id = uuid.uuid4()

    plan_old = uuid.uuid4()
    sub = MagicMock(spec=TenantSubscription)
    sub.plan_id = plan_old
    sub.status = "active"
    sub.custom_price_monthly = None
    sub.custom_price_reason = None
    sub.billing_notes = None
    sub.contracted_at = None

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = sub

    payload = mt.SubscriptionUpdate(
        plan_id=plan_old,
        custom_price_monthly=120,
        custom_price_reason="Negociação",
    )

    with patch.object(mt.audit_service, "log") as audit_log:
        mt.update_subscription(payload=payload, tenant=tenant, current_user=user, db=db)
        actions = [c.args[1] for c in audit_log.call_args_list]
    assert "subscription_updated" in actions
    assert "subscription_custom_price_updated" in actions
    assert "subscription_plan_changed" not in actions


def test_update_subscription_emits_plan_changed_audit():
    from app.api.routes import master_tenants as mt

    tenant = MagicMock(spec=Tenant)
    tenant.id = uuid.uuid4()
    user = MagicMock()
    user.id = uuid.uuid4()

    plan_old = uuid.uuid4()
    plan_new = uuid.uuid4()
    sub = MagicMock(spec=TenantSubscription)
    sub.plan_id = plan_old
    sub.status = "active"
    sub.custom_price_monthly = None
    sub.custom_price_reason = None
    sub.billing_notes = None
    sub.contracted_at = None

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = sub
    payload = mt.SubscriptionUpdate(plan_id=plan_new)

    with patch.object(mt.audit_service, "log") as audit_log:
        mt.update_subscription(payload=payload, tenant=tenant, current_user=user, db=db)
        actions = [c.args[1] for c in audit_log.call_args_list]
    assert "subscription_plan_changed" in actions
    assert "subscription_updated" in actions


def test_update_feature_emits_audit_with_old_and_new():
    from app.api.routes import master_tenants as mt

    tenant = MagicMock(spec=Tenant)
    tenant.id = uuid.uuid4()
    user = MagicMock()
    user.id = uuid.uuid4()

    flag = MagicMock(spec=TenantFeatureFlag)
    flag.enabled = False
    flag.source = "plan"
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = flag

    payload = mt.FeatureFlagUpdate(feature_key="commissions", enabled=True, source="manual")

    with patch.object(mt.audit_service, "log") as audit_log:
        mt.update_feature(payload=payload, tenant=tenant, current_user=user, db=db)
    assert audit_log.call_args.args[1] == "feature_flag_updated"
    kwargs = audit_log.call_args.kwargs
    assert kwargs["old_values"] == {"feature_key": "commissions", "enabled": False}
    assert kwargs["new_values"]["enabled"] is True


def test_update_limit_overrides_emits_per_limit_audit():
    from app.api.routes import master_tenants as mt

    tenant = MagicMock(spec=Tenant)
    tenant.id = uuid.uuid4()
    user = MagicMock()
    user.id = uuid.uuid4()

    override = MagicMock(spec=TenantLimitOverride)
    for k in LIMIT_KEYS:
        setattr(override, k, None)
    override.notes = None
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = override

    payload = mt.LimitOverrideUpdate(max_professionals=12)

    with patch.object(mt.audit_service, "log") as audit_log:
        mt.update_limit_overrides(payload=payload, tenant=tenant, current_user=user, db=db)
        actions = [c.args[1] for c in audit_log.call_args_list]
    assert "limit_override_changed" in actions
    assert "limit_override_updated" in actions
