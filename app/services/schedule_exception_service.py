"""
ScheduleException service.

Two responsibilities:
  1. CRUD over schedule_exceptions table (operator manages holidays/leaves)
  2. Check if a candidate appointment slot intersects an active exception
     — used by appointment_service.create() and reschedule().

The intersection check is purely SQL with overlap conditions
(start1 < end2) AND (end1 > start2), respecting the optional professional
and unit scope.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
import uuid
import logging

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.schedule_exception import ScheduleException
from app.core.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


class ScheduleExceptionService:
    def list_for_tenant(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        professional_id: Optional[uuid.UUID] = None,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
    ) -> List[ScheduleException]:
        q = db.query(ScheduleException).filter(
            ScheduleException.tenant_id == tenant_id,
        )
        if professional_id:
            # Pega exceções específicas do profissional + as gerais (null)
            q = q.filter(
                or_(
                    ScheduleException.professional_id == professional_id,
                    ScheduleException.professional_id.is_(None),
                ),
            )
        if from_dt:
            q = q.filter(ScheduleException.end_datetime > from_dt)
        if to_dt:
            q = q.filter(ScheduleException.start_datetime < to_dt)
        return q.order_by(ScheduleException.start_datetime.asc()).all()

    def get(
        self, db: Session, tenant_id: uuid.UUID, exception_id: uuid.UUID,
    ) -> ScheduleException:
        exc = (
            db.query(ScheduleException)
            .filter(
                ScheduleException.id == exception_id,
                ScheduleException.tenant_id == tenant_id,
            )
            .first()
        )
        if not exc:
            raise NotFoundError(
                code="SCHEDULE_EXCEPTION_NOT_FOUND",
                message="Bloqueio de horário não encontrado.",
            )
        return exc

    def create(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        data: dict,
        created_by_user_id: Optional[uuid.UUID] = None,
    ) -> ScheduleException:
        # Validate type-specific rules
        exc_type = data.get("exception_type")
        if exc_type == "leave" and not data.get("professional_id"):
            raise ValidationError(
                message="Folga (leave) requer professional_id.",
            )

        exc = ScheduleException(
            tenant_id=tenant_id,
            professional_id=data.get("professional_id"),
            unit_id=data.get("unit_id"),
            start_datetime=data["start_datetime"],
            end_datetime=data["end_datetime"],
            exception_type=exc_type,
            reason=data.get("reason"),
            created_by_user_id=created_by_user_id,
        )
        db.add(exc)
        db.commit()
        db.refresh(exc)
        return exc

    def update(
        self,
        db: Session,
        exc: ScheduleException,
        data: dict,
    ) -> ScheduleException:
        for field in (
            "professional_id", "unit_id", "start_datetime", "end_datetime",
            "exception_type", "reason",
        ):
            if field in data and data[field] is not None:
                setattr(exc, field, data[field])
        # Re-validate range
        if exc.end_datetime <= exc.start_datetime:
            raise ValidationError(
                message="end_datetime deve ser maior que start_datetime.",
            )
        if exc.exception_type == "leave" and not exc.professional_id:
            raise ValidationError(
                message="Folga (leave) requer professional_id.",
            )
        db.add(exc)
        db.commit()
        db.refresh(exc)
        return exc

    def delete(self, db: Session, exc: ScheduleException) -> None:
        db.delete(exc)
        db.commit()

    # ── Intersection check (used by appointment_service) ──────────────────────
    def find_blocking(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        professional_id: uuid.UUID,
        start_dt: datetime,
        end_dt: datetime,
        unit_id: Optional[uuid.UUID] = None,
    ) -> Optional[ScheduleException]:
        """
        Returns the first ScheduleException that blocks this slot, or None.

        Considers:
          - Tenant-wide exceptions (professional_id NULL, unit_id NULL)
          - Unit-specific exceptions (unit_id matches, professional_id NULL)
          - Professional-specific exceptions (professional_id matches)

        A slot is blocked when:
          start_dt < exc.end_datetime AND end_dt > exc.start_datetime
        """
        q = db.query(ScheduleException).filter(
            ScheduleException.tenant_id == tenant_id,
            ScheduleException.start_datetime < end_dt,
            ScheduleException.end_datetime > start_dt,
        )

        # Build the scope filter:
        #   - exception applies to this professional (or to all)
        #   - exception applies to this unit (or to all)
        scope = or_(
            ScheduleException.professional_id == professional_id,
            ScheduleException.professional_id.is_(None),
        )
        q = q.filter(scope)

        if unit_id is not None:
            q = q.filter(
                or_(
                    ScheduleException.unit_id == unit_id,
                    ScheduleException.unit_id.is_(None),
                )
            )
        else:
            # If appointment has no unit, only match exceptions also unit-less
            q = q.filter(ScheduleException.unit_id.is_(None))

        return q.first()


schedule_exception_service = ScheduleExceptionService()
