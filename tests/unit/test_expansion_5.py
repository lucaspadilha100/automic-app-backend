"""Unit tests for Expansion 5 — schedule exceptions + reschedule chain."""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

# Register full mapper graph
from tests.unit.test_expansion_1_8 import _Plan, _Tenant, _User  # noqa: F401

from app.schemas.schedule_exception import (
    ScheduleExceptionCreate, ScheduleExceptionUpdate, BulkCancelRequest,
)
from app.services.schedule_exception_service import (
    ScheduleExceptionService,
)


# ── Schema validation ────────────────────────────────────────────────────────

class TestScheduleExceptionCreateSchema:
    def test_valid_holiday(self):
        m = ScheduleExceptionCreate(
            start_datetime=datetime(2026, 12, 25, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 12, 26, 0, 0, tzinfo=timezone.utc),
            exception_type="holiday",
            reason="Natal",
        )
        assert m.exception_type == "holiday"

    def test_valid_leave_with_professional(self):
        m = ScheduleExceptionCreate(
            professional_id=uuid4(),
            start_datetime=datetime(2026, 6, 1, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 6, 8, tzinfo=timezone.utc),
            exception_type="leave",
            reason="Férias",
        )
        assert m.exception_type == "leave"

    def test_invalid_type_rejected(self):
        with pytest.raises(PydanticValidationError):
            ScheduleExceptionCreate(
                start_datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
                end_datetime=datetime(2026, 1, 2, tzinfo=timezone.utc),
                exception_type="random",
            )

    def test_end_must_be_after_start(self):
        with pytest.raises(PydanticValidationError):
            ScheduleExceptionCreate(
                start_datetime=datetime(2026, 1, 5, tzinfo=timezone.utc),
                end_datetime=datetime(2026, 1, 5, tzinfo=timezone.utc),  # equal
                exception_type="holiday",
            )

    def test_end_before_start_rejected(self):
        with pytest.raises(PydanticValidationError):
            ScheduleExceptionCreate(
                start_datetime=datetime(2026, 1, 10, tzinfo=timezone.utc),
                end_datetime=datetime(2026, 1, 5, tzinfo=timezone.utc),
                exception_type="holiday",
            )


class TestBulkCancelRequestSchema:
    def test_valid(self):
        m = BulkCancelRequest(
            professional_id=uuid4(),
            start_datetime=datetime(2026, 5, 10, 9, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 5, 10, 18, 0, tzinfo=timezone.utc),
            reason="Profissional doente",
        )
        assert m.notify_customers is True  # default

    def test_empty_reason_rejected(self):
        with pytest.raises(PydanticValidationError):
            BulkCancelRequest(
                professional_id=uuid4(),
                start_datetime=datetime(2026, 5, 10, tzinfo=timezone.utc),
                end_datetime=datetime(2026, 5, 11, tzinfo=timezone.utc),
                reason="",
            )

    def test_end_before_start_rejected(self):
        with pytest.raises(PydanticValidationError):
            BulkCancelRequest(
                professional_id=uuid4(),
                start_datetime=datetime(2026, 5, 10, 18, tzinfo=timezone.utc),
                end_datetime=datetime(2026, 5, 10, 9, tzinfo=timezone.utc),
                reason="x",
            )


# ── Service: business rules ──────────────────────────────────────────────────

class TestScheduleExceptionServiceCreate:
    def setup_method(self):
        self.svc = ScheduleExceptionService()

    def test_leave_requires_professional_id(self):
        from app.core.exceptions import ValidationError
        db = MagicMock()
        with pytest.raises(ValidationError, match="professional_id"):
            self.svc.create(
                db, uuid4(),
                {
                    "start_datetime": datetime(2026, 5, 1, tzinfo=timezone.utc),
                    "end_datetime": datetime(2026, 5, 8, tzinfo=timezone.utc),
                    "exception_type": "leave",
                    "reason": "Férias",
                },
            )

    def test_holiday_works_without_professional(self):
        db = MagicMock()
        result = self.svc.create(
            db, uuid4(),
            {
                "start_datetime": datetime(2026, 12, 25, tzinfo=timezone.utc),
                "end_datetime": datetime(2026, 12, 26, tzinfo=timezone.utc),
                "exception_type": "holiday",
                "reason": "Natal",
            },
        )
        # Successful creation: db.add then commit
        db.add.assert_called_once()
        db.commit.assert_called_once()


class TestFindBlockingMethod:
    """The find_blocking method composes the SQL query — we verify the correct
    filter combinations rather than execute a real query."""

    def setup_method(self):
        self.svc = ScheduleExceptionService()

    def test_calls_with_unit_id_filter_when_unit_provided(self):
        db = MagicMock()
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.first.return_value = None
        db.query.return_value = chain

        result = self.svc.find_blocking(
            db, tenant_id=uuid4(), professional_id=uuid4(),
            start_dt=datetime(2026, 5, 10, 9, tzinfo=timezone.utc),
            end_dt=datetime(2026, 5, 10, 10, tzinfo=timezone.utc),
            unit_id=uuid4(),
        )
        assert result is None
        # At least 3 .filter() calls: tenant+window, prof scope, unit scope
        assert chain.filter.call_count >= 3

    def test_returns_blocking_exception_when_found(self):
        db = MagicMock()
        chain = MagicMock()
        chain.filter.return_value = chain
        fake_exc = MagicMock(exception_type="holiday", reason="Natal")
        chain.first.return_value = fake_exc
        db.query.return_value = chain

        result = self.svc.find_blocking(
            db, tenant_id=uuid4(), professional_id=uuid4(),
            start_dt=datetime(2026, 12, 25, 9, tzinfo=timezone.utc),
            end_dt=datetime(2026, 12, 25, 10, tzinfo=timezone.utc),
        )
        assert result is fake_exc


class TestUpdateValidation:
    def setup_method(self):
        self.svc = ScheduleExceptionService()

    def test_update_invalid_range_rejected(self):
        from app.core.exceptions import ValidationError
        db = MagicMock()
        # Build an "existing" exception
        exc = MagicMock()
        exc.start_datetime = datetime(2026, 5, 1, tzinfo=timezone.utc)
        exc.end_datetime = datetime(2026, 5, 5, tzinfo=timezone.utc)
        exc.exception_type = "holiday"
        exc.professional_id = None

        # Attempt update with end <= start
        with pytest.raises(ValidationError, match="end_datetime"):
            self.svc.update(
                db, exc,
                {"end_datetime": datetime(2026, 4, 30, tzinfo=timezone.utc)},
            )

    def test_update_leave_without_professional_rejected(self):
        from app.core.exceptions import ValidationError
        db = MagicMock()
        exc = MagicMock()
        exc.start_datetime = datetime(2026, 5, 1, tzinfo=timezone.utc)
        exc.end_datetime = datetime(2026, 5, 5, tzinfo=timezone.utc)
        exc.exception_type = "holiday"
        exc.professional_id = None

        with pytest.raises(ValidationError, match="professional_id"):
            self.svc.update(db, exc, {"exception_type": "leave"})


# ── Reschedule chain — integration sketch ────────────────────────────────────

class TestRescheduleChainColumns:
    def test_appointment_model_has_chain_columns(self):
        """Verify the new reschedule columns exist on the model."""
        from app.models.appointment import Appointment
        cols = {c.name for c in Appointment.__table__.columns}
        assert "rescheduled_from_id" in cols
        assert "rescheduled_to_id" in cols
