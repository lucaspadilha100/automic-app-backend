"""
Testes de integração do fluxo de agendamento.
Requerem DATABASE_URL apontando para um banco real (use SQLite in-memory para CI).

Execute com:
  pytest tests/integration/ -v
"""
import pytest
from datetime import datetime, timezone, timedelta, date, time
from uuid import uuid4
from unittest.mock import MagicMock, patch

from app.services.appointment_service import appointment_service, AppointmentService
from app.services.availability_service import AvailabilityService
from app.services.package_service import PackageService
from app.core.exceptions import (
    AppointmentConflictError, ServiceNotFoundError,
    ProfessionalNotFoundError, PackageNoRemainingSessionsError,
    PackageExpiredError,
)


# ─── Helpers / Factories ───────────────────────────────────────────────────────

def make_uuid():
    return uuid4()


def make_mock_service(duration=60, price=100, buffer_before=0, buffer_after=0):
    svc = MagicMock()
    svc.id = make_uuid()
    svc.name = "Limpeza de Pele"
    svc.duration_minutes = duration
    svc.buffer_before_minutes = buffer_before
    svc.buffer_after_minutes = buffer_after
    svc.price = price
    svc.is_active = True
    return svc


def make_mock_professional(service_ids=None):
    prof = MagicMock()
    prof.id = make_uuid()
    prof.name = "Dra. Ana"
    prof.is_active = True
    prof.deleted_at = None
    links = []
    for sid in (service_ids or []):
        lk = MagicMock()
        lk.service_id = sid
        links.append(lk)
    prof.professional_services = links
    return prof


def make_mock_tenant(tz="America/Sao_Paulo"):
    t = MagicMock()
    t.id = make_uuid()
    t.timezone = tz
    t.name = "Clínica Teste"
    t.public_name = "Clínica Teste"
    t.phone = ""
    return t


def make_mock_appointment(status="scheduled", pkg_id=None):
    appt = MagicMock()
    appt.id = make_uuid()
    appt.status = status
    appt.customer_account_id = make_uuid()
    appt.tenant_customer_id = make_uuid()
    appt.professional_id = make_uuid()
    appt.tenant_id = make_uuid()
    appt.customer_package_id = pkg_id
    appt.appointment_services = []
    appt.payments = []
    return appt


# ─── Testes de Serviços ────────────────────────────────────────────────────────

class TestPackageService:

    def setup_method(self):
        self.svc = PackageService()

    def _make_cp(self, remaining=5, status="active", payment_status="paid", expires_at=None, service_ids=None):
        cp = MagicMock()
        cp.id = make_uuid()
        cp.remaining_sessions = remaining
        cp.used_sessions = 0
        cp.total_sessions = 10
        cp.status = status
        cp.payment_status = payment_status
        cp.expires_at = expires_at

        pkg = MagicMock()
        pkg.service_ids = service_ids
        cp.package = pkg
        return cp

    def test_validate_package_expired_status(self):
        db = MagicMock()
        tenant = make_mock_tenant()
        cp = self._make_cp(status="expired")
        db.query.return_value.filter.return_value.first.return_value = cp
        with pytest.raises(PackageExpiredError):
            self.svc.validate_package_use(db, tenant, cp.id, [make_uuid()])

    def test_validate_package_cancelled(self):
        from app.core.exceptions import PackageCancelledError
        db = MagicMock()
        tenant = make_mock_tenant()
        cp = self._make_cp(status="cancelled")
        db.query.return_value.filter.return_value.first.return_value = cp
        with pytest.raises(PackageCancelledError):
            self.svc.validate_package_use(db, tenant, cp.id, [make_uuid()])

    def test_validate_package_no_sessions(self):
        db = MagicMock()
        tenant = make_mock_tenant()
        cp = self._make_cp(remaining=0)
        db.query.return_value.filter.return_value.first.return_value = cp
        with pytest.raises(PackageNoRemainingSessionsError):
            self.svc.validate_package_use(db, tenant, cp.id, [make_uuid()])

    def test_validate_package_payment_pending(self):
        from app.core.exceptions import PackagePaymentPendingError
        db = MagicMock()
        tenant = make_mock_tenant()
        cp = self._make_cp(payment_status="pending")
        db.query.return_value.filter.return_value.first.return_value = cp
        with pytest.raises(PackagePaymentPendingError):
            self.svc.validate_package_use(db, tenant, cp.id, [make_uuid()])

    def test_validate_package_service_not_allowed(self):
        from app.core.exceptions import PackageServiceNotAllowedError
        db = MagicMock()
        tenant = make_mock_tenant()
        allowed_id = make_uuid()
        not_allowed_id = make_uuid()
        cp = self._make_cp(service_ids=[str(allowed_id)])

        # Configurar mock: primeira query (CP) retorna cp, segunda query (PackageService links) retorna []
        first_query = MagicMock()
        first_query.filter.return_value.first.return_value = cp

        second_query = MagicMock()
        second_query.filter.return_value.all.return_value = []  # sem links relacionais -> fallback para JSONB

        call_count = [0]
        def query_side_effect(model):
            call_count[0] += 1
            if call_count[0] == 1:
                return first_query
            return second_query

        db.query.side_effect = query_side_effect
        with pytest.raises(PackageServiceNotAllowedError):
            self.svc.validate_package_use(db, tenant, cp.id, [not_allowed_id])

    def test_validate_package_ok(self):
        db = MagicMock()
        tenant = make_mock_tenant()
        sid = make_uuid()
        cp = self._make_cp(service_ids=[str(sid)])
        db.query.return_value.filter.return_value.first.return_value = cp
        result = self.svc.validate_package_use(db, tenant, cp.id, [sid])
        assert result == cp

    def test_reserve_session_decrements(self):
        db = MagicMock()
        cp = self._make_cp(remaining=3)
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = cp

        session_obj = MagicMock()
        db.add = MagicMock()
        db.flush = MagicMock()

        self.svc.reserve_session(db, make_uuid(), cp.id, make_uuid())
        assert cp.remaining_sessions == 2

    def test_return_session_increments(self):
        db = MagicMock()
        cp = self._make_cp(remaining=2)
        cp.status = "active"
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = cp

        reserved_session = MagicMock()
        reserved_session.action = "reserved"
        db.query.return_value.filter.return_value.first.side_effect = [cp, reserved_session]

        # Override to return reserved_session for the session query
        call_count = [0]
        original_first = db.query.return_value.filter.return_value.first

        self.svc.return_session(db, make_uuid(), cp.id, make_uuid())
        # remaining_sessions incremented to 3
        assert cp.remaining_sessions == 3

    def test_consume_session_increments_used(self):
        db = MagicMock()
        cp = self._make_cp(remaining=2)
        cp.used_sessions = 3
        cp.total_sessions = 5
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = cp

        session_mock = MagicMock()
        session_mock.action = "reserved"
        db.query.return_value.filter.return_value.first.return_value = session_mock

        self.svc.consume_session(db, make_uuid(), cp.id, make_uuid())
        assert cp.used_sessions == 4

    def test_consume_session_completes_package(self):
        db = MagicMock()
        cp = self._make_cp(remaining=1)
        cp.used_sessions = 4
        cp.total_sessions = 5
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = cp

        session_mock = MagicMock()
        session_mock.action = "reserved"
        db.query.return_value.filter.return_value.first.return_value = session_mock

        self.svc.consume_session(db, make_uuid(), cp.id, make_uuid())
        assert cp.status == "fully_used"  # prompt seção 46: status é fully_used quando todas as sessões foram usadas


class TestAvailabilityEdgeCases:
    def setup_method(self):
        self.svc = AvailabilityService()

    def test_future_date_beyond_max_days_returns_empty(self):
        db = MagicMock()
        tenant = make_mock_tenant()

        import pytz
        from datetime import date

        policy = MagicMock()
        policy.slot_interval_minutes = 30
        policy.min_minutes_before_booking = 60
        policy.max_days_ahead_booking = 30

        svc_obj = make_mock_service()
        db.query.return_value.filter.return_value.first.return_value = policy
        db.query.return_value.filter.return_value.all.return_value = [svc_obj]

        far_future = date.today() + timedelta(days=90)
        result = self.svc.get_available_slots(
            db=db, tenant=tenant, service_ids=[svc_obj.id], target_date=far_future
        )
        assert result == []

    def test_validate_slot_conflict_raises(self):
        db = MagicMock()
        tenant = make_mock_tenant()

        conflicting_appt = MagicMock()
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = conflicting_appt

        now = datetime.now(timezone.utc)
        with pytest.raises(AppointmentConflictError):
            self.svc.validate_slot(db, tenant, make_uuid(), now, now + timedelta(hours=1))

    def test_validate_slot_no_conflict(self):
        db = MagicMock()
        tenant = make_mock_tenant()

        # No conflict, no block
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = None
        db.query.return_value.filter.return_value.first.return_value = None

        now = datetime.now(timezone.utc)
        # Should not raise
        self.svc.validate_slot(db, tenant, make_uuid(), now, now + timedelta(hours=1))


class TestAppointmentStatusTransitions:

    def test_confirm_changes_status(self):
        svc = AppointmentService()
        db = MagicMock()
        db.add = MagicMock()
        db.flush = MagicMock()

        appt = make_mock_appointment(status="scheduled")
        appt.status_history = []

        svc._record_status_history = MagicMock()

        # Patch audit and event services
        with patch("app.services.appointment_service.audit_service") as mock_audit, \
             patch("app.services.appointment_service.customer_event_service") as mock_event:
            result = svc.confirm(db, appt, user_id=make_uuid())
            assert result.status == "confirmed"
            assert result.confirmed_at is not None

    def test_cancel_changes_status_and_records_reason(self):
        svc = AppointmentService()
        db = MagicMock()
        db.add = MagicMock()
        db.flush = MagicMock()

        appt = make_mock_appointment(status="confirmed")
        appt.status_history = []
        appt.customer_package_id = None

        svc._record_status_history = MagicMock()

        with patch("app.services.appointment_service.audit_service"), \
             patch("app.services.appointment_service.customer_event_service"), \
             patch("app.services.appointment_service.package_service"):
            result = svc.cancel(db, appt, "user", make_uuid(), "Emergência")
            assert result.status == "cancelled"
            assert result.cancellation_reason == "Emergência"
            assert result.cancelled_at is not None

    def test_no_show_sets_correct_status(self):
        svc = AppointmentService()
        db = MagicMock()
        db.add = MagicMock()

        appt = make_mock_appointment(status="confirmed")
        appt.status_history = []

        svc._record_status_history = MagicMock()

        with patch("app.services.appointment_service.audit_service"), \
             patch("app.services.appointment_service.customer_event_service"):
            result = svc.no_show(db, appt, user_id=make_uuid())
            assert result.status == "no_show"
            assert result.no_show_at is not None

    def test_complete_sets_completed_and_timestamp(self):
        svc = AppointmentService()
        db = MagicMock()
        db.add = MagicMock()
        db.flush = MagicMock()

        appt = make_mock_appointment(status="in_progress")
        appt.customer_package_id = None
        appt.appointment_services = []
        appt.status_history = []

        svc._record_status_history = MagicMock()

        with patch("app.services.appointment_service.audit_service"), \
             patch("app.services.appointment_service.customer_event_service"), \
             patch("app.services.appointment_service.package_service"):
            result = svc.complete(db, appt, user_id=make_uuid())
            assert result.status == "completed"
            assert result.completed_at is not None
