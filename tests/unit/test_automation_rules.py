"""Unit tests for the Internal Automation Rules module."""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest

from app.main import app
from app.models.automation import AutomationRule, ActionType
from app.models.event import CustomerEvent
from app.services.automation_service import AutomationService
from app.core.exceptions import FeatureDisabledError


# ── Model field tests ─────────────────────────────────────────────────────────

def test_automation_rule_model_fields():
    assert AutomationRule.__tablename__ == "automation_rules"
    for f in ("id", "tenant_id", "name", "description", "trigger_event",
              "conditions", "action_type", "action_config", "is_active",
              "created_at", "updated_at"):
        assert hasattr(AutomationRule, f), f"Missing field: {f}"


def test_action_type_enum_values():
    assert ActionType.add_customer_tag == "add_customer_tag"
    assert ActionType.create_customer_note == "create_customer_note"
    assert ActionType.emit_webhook_event == "emit_webhook_event"
    assert ActionType.create_notification_log == "create_notification_log"


# ── Route registration ────────────────────────────────────────────────────────

def test_automation_routes_registered():
    routes = {(r.path, m) for r in app.routes if hasattr(r, "methods") for m in r.methods}
    expected = {
        ("/api/v1/admin/automations", "GET"),
        ("/api/v1/admin/automations", "POST"),
        ("/api/v1/admin/automations/{automation_id}", "GET"),
        ("/api/v1/admin/automations/{automation_id}", "PUT"),
        ("/api/v1/admin/automations/{automation_id}/status", "PATCH"),
        ("/api/v1/admin/automations/{automation_id}", "DELETE"),
    }
    missing = expected - routes
    assert not missing, f"Missing routes: {missing}"


# ── Feature flag tests ────────────────────────────────────────────────────────

def test_feature_disabled_raises():
    svc = AutomationService()
    db = MagicMock()
    tenant = MagicMock()

    with patch("app.services.automation_service.feature_flag_service") as mock_ff:
        mock_ff.require_feature.side_effect = FeatureDisabledError("automation_rules")
        with pytest.raises(FeatureDisabledError):
            svc.list_rules(db=db, tenant=tenant)


def test_create_rule_requires_feature():
    svc = AutomationService()
    db = MagicMock()
    tenant = MagicMock()

    with patch("app.services.automation_service.feature_flag_service") as mock_ff:
        mock_ff.require_feature.side_effect = FeatureDisabledError("automation_rules")
        with pytest.raises(FeatureDisabledError):
            svc.create_rule(db=db, tenant=tenant, data={})


# ── conditions_match tests ────────────────────────────────────────────────────

def _make_event(**kwargs):
    e = MagicMock(spec=CustomerEvent)
    e.event_type = kwargs.get("event_type", "customer_lifecycle_updated")
    e.entity_type = kwargs.get("entity_type", "tenant_customer")
    e.entity_id = kwargs.get("entity_id", uuid.uuid4())
    e.customer_account_id = kwargs.get("customer_account_id", uuid.uuid4())
    e.tenant_customer_id = kwargs.get("tenant_customer_id", uuid.uuid4())
    e.metadata_ = kwargs.get("metadata_", {})
    e.tenant_id = kwargs.get("tenant_id", uuid.uuid4())
    return e


def test_conditions_match_empty_conditions():
    svc = AutomationService()
    event = _make_event()
    assert svc.conditions_match(None, event) is True
    assert svc.conditions_match({}, event) is True


def test_conditions_match_metadata_field():
    svc = AutomationService()
    event = _make_event(metadata_={"lifecycle_status": "at_risk"})
    assert svc.conditions_match({"metadata.lifecycle_status": "at_risk"}, event) is True
    assert svc.conditions_match({"metadata.lifecycle_status": "vip"}, event) is False


def test_conditions_match_top_level_field():
    svc = AutomationService()
    event = _make_event(event_type="form_submitted", entity_type="custom_form")
    assert svc.conditions_match({"event_type": "form_submitted"}, event) is True
    assert svc.conditions_match({"entity_type": "tenant_customer"}, event) is False


def test_conditions_match_metadata_form_type():
    svc = AutomationService()
    event = _make_event(metadata_={"form_type": "anamnesis"})
    assert svc.conditions_match({"metadata.form_type": "anamnesis"}, event) is True
    assert svc.conditions_match({"metadata.form_type": "evaluation"}, event) is False


def test_conditions_incompatible_does_not_execute():
    """Rules with non-matching conditions must not execute."""
    svc = AutomationService()
    db = MagicMock()
    tenant_id = uuid.uuid4()
    event = _make_event(event_type="customer_lifecycle_updated",
                        metadata_={"lifecycle_status": "active"},
                        tenant_id=tenant_id)

    rule = MagicMock(spec=AutomationRule)
    rule.id = uuid.uuid4()
    rule.tenant_id = tenant_id
    rule.trigger_event = "customer_lifecycle_updated"
    rule.conditions = {"metadata.lifecycle_status": "at_risk"}  # won't match
    rule.action_type = ActionType.create_customer_note
    rule.is_active = True

    q = MagicMock()
    q.filter.return_value = q
    q.all.return_value = [rule]

    from app.models.tenant import Tenant as TenantModel
    def query_side(model):
        mq = MagicMock()
        mq.filter.return_value = mq
        if model is TenantModel:
            t = MagicMock()
            t.id = tenant_id
            mq.first.return_value = t
        else:
            mq.all.return_value = [rule]
        return mq

    db.query.side_effect = query_side

    with patch("app.services.automation_service.feature_flag_service") as mock_ff:
        mock_ff.is_enabled.return_value = True
        with patch.object(svc, "execute_action") as mock_exec:
            svc.process_customer_event(db, event)
            mock_exec.assert_not_called()


# ── execute_add_customer_tag tests ────────────────────────────────────────────

def test_execute_add_customer_tag_adds_tag():
    from app.models.customer import CustomerTag, CustomerTagLink, TenantCustomer
    svc = AutomationService()
    db = MagicMock()
    tenant_id = uuid.uuid4()
    tag_id = uuid.uuid4()
    tc_id = uuid.uuid4()

    rule = MagicMock(spec=AutomationRule)
    rule.tenant_id = tenant_id
    rule.action_config = {"tag_id": str(tag_id)}

    event = _make_event(tenant_customer_id=tc_id, tenant_id=tenant_id)

    tag = MagicMock(spec=CustomerTag)
    tag.id = tag_id

    tc = MagicMock(spec=TenantCustomer)
    tc.id = tc_id

    call_count = [0]

    def query_side(model):
        q = MagicMock()
        q.filter.return_value = q
        if call_count[0] == 0:
            q.first.return_value = tag
        elif call_count[0] == 1:
            q.first.return_value = tc
        else:
            q.first.return_value = None  # no existing link
        call_count[0] += 1
        return q

    db.query.side_effect = query_side

    svc.execute_add_customer_tag(db, rule, event)
    db.add.assert_called_once()
    added = db.add.call_args[0][0]
    assert isinstance(added, CustomerTagLink)


def test_execute_add_customer_tag_no_duplicate():
    """Tag already applied → no second CustomerTagLink created."""
    from app.models.customer import CustomerTag, CustomerTagLink, TenantCustomer
    svc = AutomationService()
    db = MagicMock()
    tenant_id = uuid.uuid4()
    tag_id = uuid.uuid4()
    tc_id = uuid.uuid4()

    rule = MagicMock(spec=AutomationRule)
    rule.tenant_id = tenant_id
    rule.action_config = {"tag_id": str(tag_id)}

    event = _make_event(tenant_customer_id=tc_id, tenant_id=tenant_id)

    tag = MagicMock(spec=CustomerTag)
    tc = MagicMock(spec=TenantCustomer)
    existing_link = MagicMock(spec=CustomerTagLink)

    call_count = [0]

    def query_side(model):
        q = MagicMock()
        q.filter.return_value = q
        if call_count[0] == 0:
            q.first.return_value = tag
        elif call_count[0] == 1:
            q.first.return_value = tc
        else:
            q.first.return_value = existing_link  # already exists
        call_count[0] += 1
        return q

    db.query.side_effect = query_side
    svc.execute_add_customer_tag(db, rule, event)
    db.add.assert_not_called()


# ── execute_create_customer_note tests ────────────────────────────────────────

def test_execute_create_customer_note():
    from app.models.customer import CustomerNote, TenantCustomer
    svc = AutomationService()
    db = MagicMock()
    tenant_id = uuid.uuid4()
    tc_id = uuid.uuid4()

    rule = MagicMock(spec=AutomationRule)
    rule.tenant_id = tenant_id
    rule.action_config = {"note": "Cliente em risco identificado", "visibility": "internal"}

    event = _make_event(tenant_customer_id=tc_id, tenant_id=tenant_id)
    tc = MagicMock(spec=TenantCustomer)

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = tc
    db.query.return_value = q

    svc.execute_create_customer_note(db, rule, event)
    db.add.assert_called_once()
    added = db.add.call_args[0][0]
    assert isinstance(added, CustomerNote)
    assert added.visibility == "internal"
    assert added.note_type == "system"


# ── execute_create_notification_log tests ─────────────────────────────────────

def test_execute_create_notification_log():
    from app.models.notification import NotificationLog
    svc = AutomationService()
    db = MagicMock()
    tenant_id = uuid.uuid4()

    rule = MagicMock(spec=AutomationRule)
    rule.tenant_id = tenant_id
    rule.action_config = {"channel": "internal", "event_type": "automation_triggered"}

    event = _make_event(tenant_id=tenant_id)
    svc.execute_create_notification_log(db, rule, event)

    db.add.assert_called_once()
    added = db.add.call_args[0][0]
    assert isinstance(added, NotificationLog)
    assert added.channel == "internal"


# ── process_customer_event safety tests ───────────────────────────────────────

def test_automation_failure_does_not_break_caller():
    """An exception in execute_action must not propagate out of process_customer_event."""
    svc = AutomationService()
    db = MagicMock()
    tenant_id = uuid.uuid4()
    event = _make_event(tenant_id=tenant_id)

    rule = MagicMock(spec=AutomationRule)
    rule.id = uuid.uuid4()
    rule.tenant_id = tenant_id
    rule.trigger_event = event.event_type
    rule.conditions = None
    rule.action_type = ActionType.create_customer_note
    rule.is_active = True

    from app.models.tenant import Tenant as TenantModel

    def query_side(model):
        q = MagicMock()
        q.filter.return_value = q
        if model is TenantModel:
            t = MagicMock()
            t.id = tenant_id
            q.first.return_value = t
        else:
            q.all.return_value = [rule]
        return q

    db.query.side_effect = query_side

    with patch("app.services.automation_service.feature_flag_service") as mock_ff, \
         patch.object(svc, "execute_action", side_effect=RuntimeError("boom")):
        mock_ff.is_enabled.return_value = True
        # Must not raise
        svc.process_customer_event(db, event)


# ── Audit log tests ───────────────────────────────────────────────────────────

def test_create_rule_calls_audit_log():
    svc = AutomationService()
    db = MagicMock()
    tenant = MagicMock()
    tenant.id = uuid.uuid4()

    with patch("app.services.automation_service.feature_flag_service"), \
         patch("app.services.automation_service.audit_service") as mock_audit:
        db.add.return_value = None
        db.flush.return_value = None
        db.commit.return_value = None
        db.refresh.side_effect = lambda obj: None

        try:
            svc.create_rule(
                db=db, tenant=tenant,
                data={"name": "Regra Teste", "trigger_event": "form_submitted",
                      "action_type": ActionType.create_customer_note,
                      "action_config": {"note": "ok"}, "is_active": True},
            )
        except Exception:
            pass

        mock_audit.log.assert_called_once()
        assert mock_audit.log.call_args.kwargs.get("action") == "automation_rule_created"


def test_set_rule_status_calls_audit_log():
    svc = AutomationService()
    db = MagicMock()
    tenant = MagicMock()
    tenant.id = uuid.uuid4()
    rule = MagicMock(spec=AutomationRule)
    rule.id = uuid.uuid4()
    rule.is_active = True

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = rule
    db.query.return_value = q

    with patch("app.services.automation_service.feature_flag_service"), \
         patch("app.services.automation_service.audit_service") as mock_audit:
        svc.set_rule_status(db=db, tenant=tenant, rule_id=rule.id, is_active=False)
        mock_audit.log.assert_called_once()
        assert "deactivated" in mock_audit.log.call_args.kwargs.get("action", "")


# ── Tenant isolation ──────────────────────────────────────────────────────────

def test_get_rule_wrong_tenant_raises():
    from app.core.exceptions import NotFoundError
    svc = AutomationService()
    db = MagicMock()
    tenant = MagicMock()
    tenant.id = uuid.uuid4()

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = None
    db.query.return_value = q

    with patch("app.services.automation_service.feature_flag_service"):
        with pytest.raises(NotFoundError):
            svc.get_rule(db=db, tenant=tenant, rule_id=uuid.uuid4())
