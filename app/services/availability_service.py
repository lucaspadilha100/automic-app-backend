from datetime import datetime, timedelta, date, time, timezone
from typing import List, Optional
from uuid import UUID
import pytz

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.appointment import Appointment
from app.models.professional import Professional, ProfessionalAvailability
from app.models.schedule import BusinessHour, BlockedTime
from app.models.service import Service
from app.models.tenant import Tenant, TenantBookingPolicy
from app.core.exceptions import (
    InvalidAvailabilityError, ProfessionalNotFoundError, ServiceNotFoundError
)


ACTIVE_STATUSES = ("scheduled", "confirmed", "in_progress", "pending_payment")


class TimeSlot:
    def __init__(self, start: datetime, end: datetime, professional_id: UUID):
        self.start = start
        self.end = end
        self.professional_id = professional_id


class AvailabilityService:

    def _tz(self, tenant: Tenant) -> pytz.timezone:
        return pytz.timezone(tenant.timezone or "America/Sao_Paulo")

    def _to_local(self, dt: datetime, tz: pytz.timezone) -> datetime:
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)
        return dt.astimezone(tz)

    def _to_utc(self, dt: datetime, tz: pytz.timezone) -> datetime:
        if dt.tzinfo is None:
            dt = tz.localize(dt)
        return dt.astimezone(pytz.utc)

    def _combine_local(self, d: date, t: time, tz: pytz.timezone) -> datetime:
        naive = datetime.combine(d, t)
        return tz.localize(naive)

    def get_available_slots(
        self,
        db: Session,
        tenant: Tenant,
        service_ids: List[UUID],
        target_date: date,
        professional_id: Optional[UUID] = None,
        any_professional: bool = False,
    ) -> List[dict]:
        tz = self._tz(tenant)

        # Load booking policy
        policy: Optional[TenantBookingPolicy] = (
            db.query(TenantBookingPolicy)
            .filter(TenantBookingPolicy.tenant_id == tenant.id)
            .first()
        )
        slot_interval = policy.slot_interval_minutes if policy else 30
        min_minutes_before = policy.min_minutes_before_booking if policy else 60
        max_days_ahead = policy.max_days_ahead_booking if policy else 60

        now_utc = datetime.now(timezone.utc)
        now_local = self._to_local(now_utc, tz)
        today_local = now_local.date()

        # Validate date range
        if target_date < today_local:
            return []
        days_ahead = (target_date - today_local).days
        if days_ahead > max_days_ahead:
            return []

        # Load services
        services = (
            db.query(Service)
            .filter(Service.id.in_(service_ids), Service.tenant_id == tenant.id, Service.is_active == True)
            .all()
        )
        if len(services) != len(service_ids):
            raise ServiceNotFoundError()

        total_duration = sum(s.duration_minutes for s in services)
        buffer_before = max((s.buffer_before_minutes for s in services), default=0)
        buffer_after = max((s.buffer_after_minutes for s in services), default=0)
        effective_duration = buffer_before + total_duration + buffer_after

        # Determine which professionals to check
        professionals = self._resolve_professionals(
            db, tenant, service_ids, professional_id, any_professional
        )
        if not professionals:
            return []

        # Get business hours for the day
        weekday = target_date.weekday()  # 0=Mon, 6=Sun
        bh: Optional[BusinessHour] = (
            db.query(BusinessHour)
            .filter(BusinessHour.tenant_id == tenant.id, BusinessHour.weekday == weekday)
            .first()
        )
        if not bh or bh.is_closed or not bh.open_time or not bh.close_time:
            return []

        business_open = self._combine_local(target_date, bh.open_time, tz)
        business_close = self._combine_local(target_date, bh.close_time, tz)

        results = []

        for prof in professionals:
            slots = self._slots_for_professional(
                db=db,
                tenant=tenant,
                professional=prof,
                target_date=target_date,
                weekday=weekday,
                tz=tz,
                effective_duration=effective_duration,
                buffer_before=buffer_before,
                slot_interval=slot_interval,
                business_open=business_open,
                business_close=business_close,
                bh=bh,
                now_local=now_local,
                min_minutes_before=min_minutes_before,
            )
            results.extend(slots)

        # Sort by start time then professional
        results.sort(key=lambda x: x["start_datetime"])
        return results

    def _resolve_professionals(
        self,
        db: Session,
        tenant: Tenant,
        service_ids: List[UUID],
        professional_id: Optional[UUID],
        any_professional: bool,
    ) -> List[Professional]:
        query = (
            db.query(Professional)
            .filter(Professional.tenant_id == tenant.id, Professional.is_active == True, Professional.deleted_at.is_(None))
        )
        if professional_id:
            query = query.filter(Professional.id == professional_id)
        professionals = query.all()

        # Filter by service capability
        filtered = []
        for prof in professionals:
            prof_service_ids = {str(ps.service_id) for ps in prof.professional_services}
            if all(str(sid) in prof_service_ids for sid in service_ids):
                filtered.append(prof)

        if professional_id and not filtered:
            raise ProfessionalNotFoundError()
        return filtered

    def _slots_for_professional(
        self,
        db: Session,
        tenant: Tenant,
        professional: Professional,
        target_date: date,
        weekday: int,
        tz: pytz.timezone,
        effective_duration: int,
        buffer_before: int,
        slot_interval: int,
        business_open: datetime,
        business_close: datetime,
        bh: BusinessHour,
        now_local: datetime,
        min_minutes_before: int,
    ) -> List[dict]:
        # Professional's own schedule
        pa: Optional[ProfessionalAvailability] = (
            db.query(ProfessionalAvailability)
            .filter(
                ProfessionalAvailability.professional_id == professional.id,
                ProfessionalAvailability.tenant_id == tenant.id,
                ProfessionalAvailability.weekday == weekday,
            )
            .first()
        )
        if pa is not None:
            if not pa.is_available or not pa.start_time or not pa.end_time:
                return []
            work_start = self._combine_local(target_date, pa.start_time, tz)
            work_end = self._combine_local(target_date, pa.end_time, tz)
        else:
            work_start = business_open
            work_end = business_close

        # Narrow to business hours
        slot_start_boundary = max(work_start, business_open)
        slot_end_boundary = min(work_end, business_close)

        if slot_start_boundary >= slot_end_boundary:
            return []

        # Collect blocked intervals for this day (UTC)
        day_start_utc = self._to_utc(
            datetime.combine(target_date, time(0, 0)), tz
        )
        day_end_utc = day_start_utc + timedelta(days=1)

        blocked_intervals = self._get_blocked_intervals(
            db, tenant, professional, day_start_utc, day_end_utc, tz
        )

        # Collect break interval
        break_intervals = []
        if bh.break_start_time and bh.break_end_time:
            b_start = self._combine_local(target_date, bh.break_start_time, tz)
            b_end = self._combine_local(target_date, bh.break_end_time, tz)
            break_intervals.append((b_start, b_end))

        if pa and pa.break_start_time and pa.break_end_time:
            pb_start = self._combine_local(target_date, pa.break_start_time, tz)
            pb_end = self._combine_local(target_date, pa.break_end_time, tz)
            break_intervals.append((pb_start, pb_end))

        # Generate candidate slots
        slots = []
        cursor = slot_start_boundary
        duration_delta = timedelta(minutes=effective_duration)
        interval_delta = timedelta(minutes=slot_interval)
        min_advance = timedelta(minutes=min_minutes_before)

        while cursor + duration_delta <= slot_end_boundary:
            slot_end = cursor + duration_delta
            slot_start_utc = self._to_utc(cursor, tz) if cursor.tzinfo else cursor
            slot_end_utc = self._to_utc(slot_end, tz) if slot_end.tzinfo else slot_end

            # Min advance check
            if cursor < now_local + min_advance:
                cursor += interval_delta
                continue

            # Break check
            overlaps_break = any(
                cursor < b_end and slot_end > b_start
                for b_start, b_end in break_intervals
            )
            if overlaps_break:
                cursor += interval_delta
                continue

            # Block check
            overlaps_block = any(
                cursor < b_end and slot_end > b_start
                for b_start, b_end in blocked_intervals
            )
            if overlaps_block:
                cursor += interval_delta
                continue

            slots.append({
                "start_datetime": cursor.astimezone(pytz.utc).isoformat(),
                "end_datetime": slot_end.astimezone(pytz.utc).isoformat(),
                "professional_id": str(professional.id),
                "professional_name": professional.name,
                "total_duration_minutes": effective_duration,
            })

            cursor += interval_delta

        return slots

    def _get_blocked_intervals(
        self,
        db: Session,
        tenant: Tenant,
        professional: Professional,
        day_start_utc: datetime,
        day_end_utc: datetime,
        tz: pytz.timezone,
    ) -> List[tuple]:
        """Returns list of (start_local, end_local) tuples covering the day."""
        # Existing appointments
        appts = (
            db.query(Appointment)
            .filter(
                Appointment.tenant_id == tenant.id,
                Appointment.professional_id == professional.id,
                Appointment.status.in_(ACTIVE_STATUSES),
                Appointment.start_datetime < day_end_utc,
                Appointment.end_datetime > day_start_utc,
            )
            .all()
        )

        # Blocked times (tenant-wide or professional-specific)
        blocks = (
            db.query(BlockedTime)
            .filter(
                BlockedTime.tenant_id == tenant.id,
                or_(
                    BlockedTime.professional_id == professional.id,
                    BlockedTime.professional_id.is_(None),
                ),
                BlockedTime.start_datetime < day_end_utc,
                BlockedTime.end_datetime > day_start_utc,
            )
            .all()
        )

        intervals = []
        for appt in appts:
            s = self._to_local(appt.start_datetime, tz)
            e = self._to_local(appt.end_datetime, tz)
            intervals.append((s, e))

        for block in blocks:
            s = self._to_local(block.start_datetime, tz)
            e = self._to_local(block.end_datetime, tz)
            intervals.append((s, e))

        return intervals

    def validate_slot(
        self,
        db: Session,
        tenant: Tenant,
        professional_id: UUID,
        start_datetime: datetime,
        end_datetime: datetime,
    ) -> None:
        """Re-validate availability immediately before booking (concurrency guard)."""
        tz = self._tz(tenant)

        # Check active appointment conflict using SELECT FOR UPDATE
        conflict = (
            db.query(Appointment)
            .filter(
                Appointment.tenant_id == tenant.id,
                Appointment.professional_id == professional_id,
                Appointment.status.in_(ACTIVE_STATUSES),
                Appointment.start_datetime < end_datetime,
                Appointment.end_datetime > start_datetime,
            )
            .with_for_update()
            .first()
        )
        if conflict:
            from app.core.exceptions import AppointmentConflictError
            raise AppointmentConflictError()

        # Check blocked times
        block = (
            db.query(BlockedTime)
            .filter(
                BlockedTime.tenant_id == tenant.id,
                or_(
                    BlockedTime.professional_id == professional_id,
                    BlockedTime.professional_id.is_(None),
                ),
                BlockedTime.start_datetime < end_datetime,
                BlockedTime.end_datetime > start_datetime,
            )
            .first()
        )
        if block:
            raise InvalidAvailabilityError("O horário está bloqueado.")


availability_service = AvailabilityService()
