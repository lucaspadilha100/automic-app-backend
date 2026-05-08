import pytest
from datetime import date, datetime, time, timezone
from unittest.mock import MagicMock, patch, PropertyMock
from uuid import uuid4
import pytz

from app.services.availability_service import AvailabilityService
from app.models.tenant import Tenant, TenantBookingPolicy
from app.models.professional import Professional, ProfessionalAvailability
from app.models.schedule import BusinessHour
from app.models.service import Service, ProfessionalService
from app.models.appointment import Appointment


def make_tenant():
    t = MagicMock(spec=Tenant)
    t.id = uuid4()
    t.timezone = "America/Sao_Paulo"
    return t


def make_service(duration=60):
    svc = MagicMock(spec=Service)
    svc.id = uuid4()
    svc.duration_minutes = duration
    svc.buffer_before_minutes = 0
    svc.buffer_after_minutes = 0
    svc.price = 100
    svc.is_active = True
    return svc


def make_professional():
    p = MagicMock(spec=Professional)
    p.id = uuid4()
    p.name = "Dr. Teste"
    p.is_active = True
    p.deleted_at = None
    p.professional_services = []
    p.availability = []
    return p


class TestAvailabilityServiceMath:
    def setup_method(self):
        self.svc = AvailabilityService()

    def test_to_utc_round_trip(self):
        tz = pytz.timezone("America/Sao_Paulo")
        naive_dt = datetime(2024, 6, 1, 10, 0)
        local = tz.localize(naive_dt)
        utc = self.svc._to_utc(local, tz)
        back = self.svc._to_local(utc, tz)
        assert back.hour == 10
        assert back.minute == 0

    def test_combine_local(self):
        tz = pytz.timezone("America/Sao_Paulo")
        d = date(2024, 6, 1)
        t = time(9, 0)
        result = self.svc._combine_local(d, t, tz)
        assert result.tzinfo is not None
        assert result.hour == 9

    def test_blocked_intervals_empty(self):
        """Sem agendamentos nem bloqueios, retorna lista vazia."""
        db = MagicMock()
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = None
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.first.return_value = None

        tenant = make_tenant()
        professional = make_professional()
        tz = pytz.timezone("America/Sao_Paulo")

        day_start = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)
        day_end = datetime(2024, 6, 1, 23, 59, tzinfo=timezone.utc)

        intervals = self.svc._get_blocked_intervals(db, tenant, professional, day_start, day_end, tz)
        assert isinstance(intervals, list)


class TestAvailabilityPolicyRules:
    def test_past_date_returns_empty(self):
        """Data passada retorna lista vazia sem queries."""
        svc_instance = AvailabilityService()
        db = MagicMock()
        tenant = make_tenant()
        service = make_service()
        service_id = service.id

        # Mock query chain
        db.query.return_value.filter.return_value.first.return_value = MagicMock(
            slot_interval_minutes=30,
            min_minutes_before_booking=60,
            max_days_ahead_booking=60,
        )
        db.query.return_value.filter.return_value.all.return_value = [service]

        result = svc_instance.get_available_slots(
            db=db,
            tenant=tenant,
            service_ids=[service_id],
            target_date=date(2020, 1, 1),  # past date
        )
        assert result == []
