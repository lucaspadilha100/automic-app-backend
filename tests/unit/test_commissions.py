"""Unit tests for the Professional Commissions module."""
import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.main import app
from app.models.commission import (
    ProfessionalCommissionSetting, CommissionRecord,
    CommissionType, CommissionStatus,
)
from app.services.commission_service import CommissionService


# ── Model field tests ─────────────────────────────────────────────────────────

def test_commission_setting_model_fields():
    assert ProfessionalCommissionSetting.__tablename__ == "professional_commission_settings"
    for f in ("id", "tenant_id", "professional_id", "commission_type",
              "commission_value", "is_active", "created_at", "updated_at"):
        assert hasattr(ProfessionalCommissionSetting, f), f"Missing field: {f}"


def test_commission_record_model_fields():
    assert CommissionRecord.__tablename__ == "commission_records"
    for f in ("id", "tenant_id", "appointment_id", "professional_id",
              "base_amount", "commission_type", "commission_value",
              "commission_amount", "status", "created_at", "updated_at"):
        assert hasattr(CommissionRecord, f), f"Missing field: {f}"


def test_commission_type_enum_values():
    assert CommissionType.percentage == "percentage"
    assert CommissionType.fixed == "fixed"
    assert CommissionType.none == "none"


def test_commission_status_enum_values():
    assert CommissionStatus.pending == "pending"
    assert CommissionStatus.paid == "paid"
    assert CommissionStatus.cancelled == "cancelled"


# ── Route registration tests ──────────────────────────────────────────────────

def test_admin_commission_routes_registered():
    routes = {
        (route.path, method)
        for route in app.routes
        if hasattr(route, "methods")
        for method in route.methods
    }
    expected = {
        ("/api/v1/admin/commissions/settings", "GET"),
        ("/api/v1/admin/commissions/settings", "POST"),
        ("/api/v1/admin/commissions/settings/{setting_id}", "GET"),
        ("/api/v1/admin/commissions/settings/{setting_id}", "PUT"),
        ("/api/v1/admin/commissions/settings/{setting_id}/status", "PATCH"),
        ("/api/v1/admin/commissions/records", "GET"),
        ("/api/v1/admin/commissions/records/{record_id}", "GET"),
        ("/api/v1/admin/commissions/records/{record_id}/mark-paid", "POST"),
        ("/api/v1/admin/commissions/records/{record_id}/cancel", "POST"),
    }
    missing = expected - routes
    assert not missing, f"Missing routes: {missing}"


# ── Service calculation tests ─────────────────────────────────────────────────

def test_calculate_amount_percentage():
    svc = CommissionService()
    result = svc._calculate_amount(CommissionType.percentage, Decimal("10"), Decimal("500"))
    assert result == Decimal("50.00")


def test_calculate_amount_percentage_zero_base():
    svc = CommissionService()
    result = svc._calculate_amount(CommissionType.percentage, Decimal("20"), Decimal("0"))
    assert result == Decimal("0.00")


def test_calculate_amount_fixed():
    svc = CommissionService()
    result = svc._calculate_amount(CommissionType.fixed, Decimal("75.50"), Decimal("999"))
    assert result == Decimal("75.50")


def test_calculate_amount_none():
    svc = CommissionService()
    result = svc._calculate_amount(CommissionType.none, Decimal("20"), Decimal("500"))
    assert result == Decimal("0")


# ── generate_for_appointment tests ────────────────────────────────────────────

def _make_appointment(tenant_id=None, professional_id=None, total_price="300.00"):
    a = MagicMock()
    a.id = uuid.uuid4()
    a.tenant_id = tenant_id or uuid.uuid4()
    a.professional_id = professional_id or uuid.uuid4()
    a.total_price = Decimal(total_price)
    a.customer_account_id = uuid.uuid4()
    a.tenant_customer_id = uuid.uuid4()
    return a


def _make_setting(tenant_id, professional_id, commission_type, commission_value, is_active=True):
    s = MagicMock(spec=ProfessionalCommissionSetting)
    s.tenant_id = tenant_id
    s.professional_id = professional_id
    s.commission_type = commission_type
    s.commission_value = Decimal(str(commission_value))
    s.is_active = is_active
    return s


def test_generate_for_appointment_percentage():
    svc = CommissionService()
    db = MagicMock()
    appt = _make_appointment(total_price="200.00")
    setting = _make_setting(appt.tenant_id, appt.professional_id, CommissionType.percentage, "10")

    call_count = [0]

    def query_side(model):
        q = MagicMock()
        q.filter.return_value = q
        if call_count[0] == 0:
            q.first.return_value = None    # no existing record
        else:
            q.first.return_value = setting  # active setting
        call_count[0] += 1
        return q

    db.query.side_effect = query_side
    db.add.return_value = None
    db.flush.return_value = None

    record = svc.generate_for_appointment(db, appt)
    assert record is not None
    db.add.assert_called_once()
    added = db.add.call_args[0][0]
    assert added.commission_amount == Decimal("20.00")
    assert added.commission_type == CommissionType.percentage


def test_generate_for_appointment_fixed():
    svc = CommissionService()
    db = MagicMock()
    appt = _make_appointment(total_price="500.00")
    setting = _make_setting(appt.tenant_id, appt.professional_id, CommissionType.fixed, "50")

    call_count = [0]

    def query_side(model):
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = None if call_count[0] == 0 else setting
        call_count[0] += 1
        return q

    db.query.side_effect = query_side
    db.add.return_value = None
    db.flush.return_value = None

    record = svc.generate_for_appointment(db, appt)
    added = db.add.call_args[0][0]
    assert added.commission_amount == Decimal("50.00")
    assert added.commission_type == CommissionType.fixed


def test_generate_for_appointment_none_type_creates_no_record():
    svc = CommissionService()
    db = MagicMock()
    appt = _make_appointment()
    setting = _make_setting(appt.tenant_id, appt.professional_id, CommissionType.none, "0")

    call_count = [0]

    def query_side(model):
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = None if call_count[0] == 0 else setting
        call_count[0] += 1
        return q

    db.query.side_effect = query_side
    result = svc.generate_for_appointment(db, appt)
    assert result is None
    db.add.assert_not_called()


def test_generate_for_appointment_no_setting_creates_no_record():
    svc = CommissionService()
    db = MagicMock()
    appt = _make_appointment()

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = None  # no existing record AND no setting
    db.query.return_value = q

    result = svc.generate_for_appointment(db, appt)
    assert result is None
    db.add.assert_not_called()


def test_generate_for_appointment_no_duplicate():
    """generate_for_appointment returns existing record without creating new one."""
    svc = CommissionService()
    db = MagicMock()
    appt = _make_appointment()
    existing_record = MagicMock(spec=CommissionRecord)

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = existing_record  # record already exists
    db.query.return_value = q

    result = svc.generate_for_appointment(db, appt)
    assert result is existing_record
    db.add.assert_not_called()


# ── mark_paid / cancel tests ──────────────────────────────────────────────────

def test_mark_paid_transitions_pending_to_paid():
    svc = CommissionService()
    db = MagicMock()
    tenant_id = uuid.uuid4()
    record = MagicMock(spec=CommissionRecord)
    record.id = uuid.uuid4()
    record.tenant_id = tenant_id
    record.status = CommissionStatus.pending

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = record
    db.query.return_value = q

    with patch("app.services.commission_service.audit_service"):
        svc.mark_paid(db=db, tenant_id=tenant_id, record_id=record.id)

    assert record.status == CommissionStatus.paid


def test_mark_paid_rejects_non_pending():
    from app.core.exceptions import ValidationError
    svc = CommissionService()
    db = MagicMock()
    tenant_id = uuid.uuid4()
    record = MagicMock(spec=CommissionRecord)
    record.id = uuid.uuid4()
    record.tenant_id = tenant_id
    record.status = CommissionStatus.paid  # already paid

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = record
    db.query.return_value = q

    with pytest.raises(ValidationError):
        svc.mark_paid(db=db, tenant_id=tenant_id, record_id=record.id)


def test_cancel_record():
    svc = CommissionService()
    db = MagicMock()
    tenant_id = uuid.uuid4()
    record = MagicMock(spec=CommissionRecord)
    record.id = uuid.uuid4()
    record.tenant_id = tenant_id
    record.status = CommissionStatus.pending

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = record
    db.query.return_value = q

    with patch("app.services.commission_service.audit_service"):
        svc.cancel_record(db=db, tenant_id=tenant_id, record_id=record.id)

    assert record.status == CommissionStatus.cancelled


def test_cancel_already_cancelled_raises():
    from app.core.exceptions import ValidationError
    svc = CommissionService()
    db = MagicMock()
    tenant_id = uuid.uuid4()
    record = MagicMock(spec=CommissionRecord)
    record.id = uuid.uuid4()
    record.status = CommissionStatus.cancelled

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = record
    db.query.return_value = q

    with pytest.raises(ValidationError):
        svc.cancel_record(db=db, tenant_id=tenant_id, record_id=record.id)


# ── Audit log tests ───────────────────────────────────────────────────────────

def test_create_setting_calls_audit_log():
    svc = CommissionService()
    db = MagicMock()
    tenant_id = uuid.uuid4()
    professional_id = uuid.uuid4()

    # Professional validation query
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = MagicMock()  # professional found
    db.query.return_value = q

    with patch("app.services.commission_service.audit_service") as mock_audit:
        try:
            svc.create_setting(
                db=db,
                tenant_id=tenant_id,
                data={
                    "professional_id": professional_id,
                    "commission_type": CommissionType.percentage,
                    "commission_value": Decimal("15"),
                    "is_active": True,
                },
            )
        except Exception:
            pass
        mock_audit.log.assert_called_once()
        assert mock_audit.log.call_args.kwargs.get("action") == "commission_setting_created"


def test_mark_paid_calls_audit_log():
    svc = CommissionService()
    db = MagicMock()
    tenant_id = uuid.uuid4()
    record = MagicMock(spec=CommissionRecord)
    record.id = uuid.uuid4()
    record.status = CommissionStatus.pending

    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = record
    db.query.return_value = q

    with patch("app.services.commission_service.audit_service") as mock_audit:
        svc.mark_paid(db=db, tenant_id=tenant_id, record_id=record.id)
        mock_audit.log.assert_called_once()
        assert mock_audit.log.call_args.kwargs.get("action") == "commission_marked_paid"


# ── Tenant isolation ──────────────────────────────────────────────────────────

def test_get_setting_wrong_tenant_raises_not_found():
    from app.core.exceptions import NotFoundError
    svc = CommissionService()
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = None
    db.query.return_value = q

    with pytest.raises(NotFoundError):
        svc.get_setting(db=db, tenant_id=uuid.uuid4(), setting_id=uuid.uuid4())


def test_get_record_wrong_tenant_raises_not_found():
    from app.core.exceptions import NotFoundError
    svc = CommissionService()
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = None
    db.query.return_value = q

    with pytest.raises(NotFoundError):
        svc.get_record(db=db, tenant_id=uuid.uuid4(), record_id=uuid.uuid4())
