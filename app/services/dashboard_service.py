from datetime import datetime, timezone, date, timedelta
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from app.models.appointment import Appointment
from app.models.customer import TenantCustomer
from app.models.payment import Payment
from app.models.professional import ProfessionalAvailability


class DashboardService:

    def get_summary(
        self, db: Session, tenant_id: UUID,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        professional_id: Optional[UUID] = None,
    ) -> dict:
        now = datetime.now(timezone.utc)
        today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        today_end = today_start + timedelta(days=1)
        week_start = today_start - timedelta(days=today_start.weekday())
        week_end = week_start + timedelta(days=7)
        month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)

        # Today's appointments list
        todays_q = (
            db.query(Appointment)
            .options(
                joinedload(Appointment.appointment_services),
                joinedload(Appointment.customer_account),
            )
            .filter(
                Appointment.tenant_id == tenant_id,
                Appointment.start_datetime >= today_start,
                Appointment.start_datetime < today_end,
                Appointment.status.notin_(["cancelled", "no_show"]),
            )
        )
        if professional_id:
            todays_q = todays_q.filter(Appointment.professional_id == professional_id)
        todays_list = todays_q.order_by(Appointment.start_datetime).all()

        # This week count
        week_q = db.query(func.count(Appointment.id)).filter(
            Appointment.tenant_id == tenant_id,
            Appointment.start_datetime >= week_start,
            Appointment.start_datetime < week_end,
            Appointment.status.notin_(["cancelled", "no_show"]),
        )
        if professional_id:
            week_q = week_q.filter(Appointment.professional_id == professional_id)
        appointments_this_week = week_q.scalar() or 0

        # Status counts
        base = db.query(Appointment).filter(Appointment.tenant_id == tenant_id)
        if professional_id:
            base = base.filter(Appointment.professional_id == professional_id)
        if date_from:
            base = base.filter(Appointment.start_datetime >= datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc))
        if date_to:
            base = base.filter(Appointment.start_datetime < datetime(date_to.year, date_to.month, date_to.day, tzinfo=timezone.utc) + timedelta(days=1))

        confirmed_count = base.filter(Appointment.status == "confirmed").count()
        cancelled_count = base.filter(Appointment.status == "cancelled").count()
        no_show_count = base.filter(Appointment.status == "no_show").count()

        # Revenue this month from payments table
        revenue_this_month = db.query(func.sum(Payment.amount)).filter(
            Payment.tenant_id == tenant_id,
            Payment.status == "paid",
            Payment.paid_at >= month_start,
            Payment.paid_at < next_month,
        ).scalar() or 0

        total_customers = db.query(TenantCustomer).filter(TenantCustomer.tenant_id == tenant_id).count()

        # Occupancy rate: booked minutes / total available minutes this month
        booked_minutes = db.query(func.sum(Appointment.total_duration_minutes)).filter(
            Appointment.tenant_id == tenant_id,
            Appointment.start_datetime >= month_start,
            Appointment.start_datetime < next_month,
            Appointment.status.notin_(["cancelled", "no_show"]),
        ).scalar() or 0

        availabilities = db.query(ProfessionalAvailability).filter(
            ProfessionalAvailability.tenant_id == tenant_id,
            ProfessionalAvailability.is_available == True,
        ).all()

        total_available_minutes = 0
        if availabilities:
            current_day = month_start.date()
            end_day = next_month.date()
            while current_day < end_day:
                weekday = current_day.weekday()  # 0=Mon, 6=Sun
                for av in availabilities:
                    if av.weekday == weekday and av.start_time and av.end_time:
                        start_m = av.start_time.hour * 60 + av.start_time.minute
                        end_m = av.end_time.hour * 60 + av.end_time.minute
                        duration = end_m - start_m
                        if av.break_start_time and av.break_end_time:
                            duration -= (
                                av.break_end_time.hour * 60 + av.break_end_time.minute
                                - av.break_start_time.hour * 60 - av.break_start_time.minute
                            )
                        total_available_minutes += max(0, duration)
                current_day += timedelta(days=1)

        occupancy_rate = round(booked_minutes / total_available_minutes * 100, 1) if total_available_minutes > 0 else 0

        todays_serialized = [
            {
                "id": str(a.id),
                "start_datetime": a.start_datetime.isoformat(),
                "status": a.status,
                "customer_name": a.customer_account.name if a.customer_account else None,
                "appointment_services": [
                    {"service_name_snapshot": s.service_name_snapshot}
                    for s in (a.appointment_services or [])
                ],
            }
            for a in todays_list
        ]

        return {
            "appointments_today": len(todays_list),
            "appointments_this_week": appointments_this_week,
            "total_customers": total_customers,
            "revenue_this_month": float(revenue_this_month),
            "confirmed_count": confirmed_count,
            "cancelled_count": cancelled_count,
            "no_show_count": no_show_count,
            "occupancy_rate": occupancy_rate,
            "todays_appointments": todays_serialized,
        }


dashboard_service = DashboardService()
