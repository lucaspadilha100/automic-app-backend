from datetime import datetime, timezone, date
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.models.appointment import Appointment
from app.models.customer import TenantCustomer


class DashboardService:

    def get_summary(
        self, db: Session, tenant_id: UUID,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        professional_id: Optional[UUID] = None,
    ) -> dict:
        from datetime import timedelta
        import pytz

        now = datetime.now(timezone.utc)
        today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        today_end = today_start + timedelta(days=1)

        base = db.query(Appointment).filter(Appointment.tenant_id == tenant_id)
        if professional_id:
            base = base.filter(Appointment.professional_id == professional_id)

        if date_from:
            dt_from = datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc)
            base = base.filter(Appointment.start_datetime >= dt_from)
        if date_to:
            dt_to = datetime(date_to.year, date_to.month, date_to.day, tzinfo=timezone.utc) + timedelta(days=1)
            base = base.filter(Appointment.start_datetime < dt_to)

        today_appointments = (
            db.query(Appointment)
            .filter(
                Appointment.tenant_id == tenant_id,
                Appointment.start_datetime >= today_start,
                Appointment.start_datetime < today_end,
                Appointment.status.notin_(["cancelled", "no_show"]),
            )
            .count()
        )

        upcoming = (
            db.query(Appointment)
            .filter(
                Appointment.tenant_id == tenant_id,
                Appointment.start_datetime >= now,
                Appointment.status.in_(["scheduled", "confirmed"]),
            )
            .count()
        )

        total = base.count()
        completed = base.filter(Appointment.status == "completed").count()
        cancelled = base.filter(Appointment.status == "cancelled").count()
        no_shows = base.filter(Appointment.status == "no_show").count()

        revenue_confirmed = (
            base.filter(Appointment.status == "completed")
            .with_entities(func.sum(Appointment.total_price))
            .scalar() or 0
        )
        revenue_expected = (
            base.filter(Appointment.status.in_(["scheduled", "confirmed"]))
            .with_entities(func.sum(Appointment.total_price))
            .scalar() or 0
        )

        new_customers = db.query(TenantCustomer).filter(TenantCustomer.tenant_id == tenant_id).count()

        return {
            "today_appointments": today_appointments,
            "upcoming_appointments": upcoming,
            "total_appointments": total,
            "completed_appointments": completed,
            "cancelled_appointments": cancelled,
            "no_shows": no_shows,
            "revenue_confirmed": float(revenue_confirmed),
            "revenue_expected": float(revenue_expected),
            "total_customers": new_customers,
        }


dashboard_service = DashboardService()
