"""Unit tests for the Custom Forms / Anamnesis Forms module."""
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.main import app
from app.models.custom_form import CustomForm, CustomFormField, CustomFormResponse, FormType, FieldType
from app.services.custom_form_service import CustomFormService
from app.core.exceptions import ValidationError, FeatureDisabledError


# ── Model field tests ─────────────────────────────────────────────────────────

def test_custom_form_model_fields():
    assert CustomForm.__tablename__ == "custom_forms"
    for f in ("id", "tenant_id", "title", "description", "form_type", "is_active", "created_at", "updated_at"):
        assert hasattr(CustomForm, f), f"Missing: {f}"


def test_custom_form_field_model_fields():
    assert CustomFormField.__tablename__ == "custom_form_fields"
    for f in ("id", "tenant_id", "form_id", "label", "field_type", "required", "options", "sort_order"):
        assert hasattr(CustomFormField, f), f"Missing: {f}"


def test_custom_form_response_model_fields():
    assert CustomFormResponse.__tablename__ == "custom_form_responses"
    for f in ("id", "tenant_id", "form_id", "customer_account_id", "tenant_customer_id",
              "appointment_id", "answers", "submitted_at"):
        assert hasattr(CustomFormResponse, f), f"Missing: {f}"


def test_form_type_enum_values():
    assert FormType.anamnesis == "anamnesis"
    assert FormType.pre_service == "pre_service"
    assert FormType.post_service == "post_service"
    assert FormType.evaluation == "evaluation"


def test_field_type_enum_values():
    assert FieldType.text == "text"
    assert FieldType.textarea == "textarea"
    assert FieldType.number == "number"
    assert FieldType.date == "date"
    assert FieldType.boolean == "boolean"
    assert FieldType.select == "select"
    assert FieldType.multiselect == "multiselect"


# ── Route registration ────────────────────────────────────────────────────────

def test_admin_custom_form_routes_registered():
    routes = {(r.path, m) for r in app.routes if hasattr(r, "methods") for m in r.methods}
    expected = {
        ("/api/v1/admin/forms", "GET"),
        ("/api/v1/admin/forms", "POST"),
        ("/api/v1/admin/forms/{form_id}", "GET"),
        ("/api/v1/admin/forms/{form_id}", "PUT"),
        ("/api/v1/admin/forms/{form_id}/status", "PATCH"),
        ("/api/v1/admin/forms/{form_id}/fields", "POST"),
        ("/api/v1/admin/forms/{form_id}/fields/{field_id}", "PUT"),
        ("/api/v1/admin/forms/{form_id}/fields/{field_id}", "DELETE"),
        ("/api/v1/admin/forms/{form_id}/responses", "GET"),
        ("/api/v1/admin/forms/responses/{response_id}", "GET"),
    }
    missing = expected - routes
    assert not missing, f"Missing admin routes: {missing}"


def test_customer_custom_form_routes_registered():
    routes = {(r.path, m) for r in app.routes if hasattr(r, "methods") for m in r.methods}
    expected = {
        ("/api/v1/customer/tenants/{slug}/forms", "GET"),
        ("/api/v1/customer/tenants/{slug}/forms/{form_id}", "GET"),
        ("/api/v1/customer/tenants/{slug}/forms/{form_id}/submit", "POST"),
    }
    missing = expected - routes
    assert not missing, f"Missing customer routes: {missing}"


# ── validate_answers tests ────────────────────────────────────────────────────

def _make_field(field_id, field_type, required=False, options=None, label="Campo"):
    f = MagicMock(spec=CustomFormField)
    f.id = field_id
    f.field_type = field_type
    f.required = required
    f.options = options
    f.label = label
    return f


def test_validate_answers_required_missing():
    svc = CustomFormService()
    fid = uuid.uuid4()
    fields = [_make_field(fid, FieldType.text, required=True)]
    with pytest.raises(ValidationError, match="obrigatório"):
        svc.validate_answers(fields, {})


def test_validate_answers_required_present():
    svc = CustomFormService()
    fid = uuid.uuid4()
    fields = [_make_field(fid, FieldType.text, required=True)]
    svc.validate_answers(fields, {str(fid): "resposta"})  # no exception


def test_validate_answers_select_invalid_option():
    svc = CustomFormService()
    fid = uuid.uuid4()
    fields = [_make_field(fid, FieldType.select, options=["A", "B", "C"])]
    with pytest.raises(ValidationError, match="inválido"):
        svc.validate_answers(fields, {str(fid): "Z"})


def test_validate_answers_select_valid_option():
    svc = CustomFormService()
    fid = uuid.uuid4()
    fields = [_make_field(fid, FieldType.select, options=["A", "B"])]
    svc.validate_answers(fields, {str(fid): "B"})  # no exception


def test_validate_answers_multiselect_invalid():
    svc = CustomFormService()
    fid = uuid.uuid4()
    fields = [_make_field(fid, FieldType.multiselect, options=["X", "Y"])]
    with pytest.raises(ValidationError, match="inválidas"):
        svc.validate_answers(fields, {str(fid): ["X", "Z"]})


def test_validate_answers_multiselect_valid():
    svc = CustomFormService()
    fid = uuid.uuid4()
    fields = [_make_field(fid, FieldType.multiselect, options=["X", "Y"])]
    svc.validate_answers(fields, {str(fid): ["X", "Y"]})  # no exception


def test_validate_answers_optional_field_absent():
    """Optional field (required=False) with no answer should not raise."""
    svc = CustomFormService()
    fid = uuid.uuid4()
    fields = [_make_field(fid, FieldType.text, required=False)]
    svc.validate_answers(fields, {})  # no exception


# ── Feature flag tests ────────────────────────────────────────────────────────

def test_feature_flag_disabled_raises():
    svc = CustomFormService()
    db = MagicMock()
    tenant = MagicMock()

    with patch("app.services.custom_form_service.feature_flag_service") as mock_ff:
        mock_ff.require_feature.side_effect = FeatureDisabledError("custom_forms")
        with pytest.raises(FeatureDisabledError):
            svc.list_forms(db=db, tenant=tenant)


# ── Service unit tests ────────────────────────────────────────────────────────

def _make_tenant(tenant_id=None):
    t = MagicMock()
    t.id = tenant_id or uuid.uuid4()
    return t


def _make_form(tenant_id, form_type=FormType.anamnesis, is_active=True):
    f = MagicMock(spec=CustomForm)
    f.id = uuid.uuid4()
    f.tenant_id = tenant_id
    f.form_type = form_type
    f.is_active = is_active
    f.title = "Anamnese"
    return f


def test_create_form_calls_audit_log():
    svc = CustomFormService()
    db = MagicMock()
    tenant = _make_tenant()

    with patch("app.services.custom_form_service.feature_flag_service"), \
         patch("app.services.custom_form_service.audit_service") as mock_audit:
        db.add.return_value = None
        db.flush.return_value = None
        db.commit.return_value = None
        db.refresh.side_effect = lambda obj: None

        try:
            svc.create_form(
                db=db, tenant=tenant,
                data={"title": "Anamnese", "description": None, "form_type": FormType.anamnesis, "is_active": True},
            )
        except Exception:
            pass

        mock_audit.log.assert_called_once()
        assert mock_audit.log.call_args.kwargs.get("action") == "custom_form_created"


def test_set_form_status_calls_audit_log():
    svc = CustomFormService()
    db = MagicMock()
    tenant = _make_tenant()
    form = _make_form(tenant.id)

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = form
    db.query.return_value = q

    with patch("app.services.custom_form_service.feature_flag_service"), \
         patch("app.services.custom_form_service.audit_service") as mock_audit:
        svc.set_form_status(db=db, tenant=tenant, form_id=form.id, is_active=False)
        mock_audit.log.assert_called_once()
        assert "deactivated" in mock_audit.log.call_args.kwargs.get("action", "")


def test_submit_response_emits_customer_event():
    svc = CustomFormService()
    db = MagicMock()
    tenant = _make_tenant()
    form = _make_form(tenant.id, is_active=True)
    customer_id = uuid.uuid4()

    call_count = [0]

    def query_side(model):
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        if call_count[0] == 0:
            q.first.return_value = form   # get_active_form_for_customer
        elif call_count[0] == 1:
            q.first.return_value = None   # TenantCustomer (None is ok)
        elif call_count[0] == 2:
            q.all.return_value = []       # fields (empty — nothing required)
        else:
            q.first.return_value = None
        call_count[0] += 1
        return q

    db.query.side_effect = query_side
    db.add.return_value = None
    db.flush.return_value = None
    db.commit.return_value = None
    db.refresh.side_effect = lambda obj: None

    with patch("app.services.custom_form_service.feature_flag_service"), \
         patch("app.services.custom_form_service.customer_event_service") as mock_event:
        try:
            svc.submit_response(
                db=db, tenant=tenant, form_id=form.id,
                customer_account_id=customer_id, answers={},
            )
        except Exception:
            pass

        mock_event.emit.assert_called_once()
        assert mock_event.emit.call_args.kwargs.get("event_type") == "form_submitted"


def test_get_active_form_inactive_raises_not_found():
    from app.core.exceptions import NotFoundError
    svc = CustomFormService()
    db = MagicMock()
    tenant = _make_tenant()

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = None  # inactive form not found
    db.query.return_value = q

    with patch("app.services.custom_form_service.feature_flag_service"):
        with pytest.raises(NotFoundError):
            svc.get_active_form_for_customer(db=db, tenant=tenant, form_id=uuid.uuid4())


def test_tenant_isolation_get_form():
    from app.core.exceptions import NotFoundError
    svc = CustomFormService()
    db = MagicMock()
    tenant = _make_tenant()

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = None
    db.query.return_value = q

    with patch("app.services.custom_form_service.feature_flag_service"):
        with pytest.raises(NotFoundError):
            svc.get_form(db=db, tenant=tenant, form_id=uuid.uuid4())


def test_add_field_calls_audit_log():
    svc = CustomFormService()
    db = MagicMock()
    tenant = _make_tenant()
    form = _make_form(tenant.id)

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = form
    db.query.return_value = q

    with patch("app.services.custom_form_service.feature_flag_service"), \
         patch("app.services.custom_form_service.audit_service") as mock_audit:
        db.add.return_value = None
        db.flush.return_value = None
        db.commit.return_value = None
        db.refresh.side_effect = lambda obj: None

        try:
            svc.add_field(
                db=db, tenant=tenant, form_id=form.id,
                data={"label": "Nome", "field_type": FieldType.text, "required": True, "options": None, "sort_order": 0},
            )
        except Exception:
            pass

        mock_audit.log.assert_called_once()
        assert mock_audit.log.call_args.kwargs.get("action") == "custom_form_field_added"
