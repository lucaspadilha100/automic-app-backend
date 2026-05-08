from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
import uuid

from db.session import get_db
from app.core.dependencies import get_current_user, require_active_tenant, require_manager_or_above
from app.models.user import User
from app.models.tenant import Tenant
from app.models.appointment import Appointment
from app.models.customer import TenantCustomer
from app.models.professional import Professional
from app.models.service import Service
from app.services.dashboard_service import dashboard_service
from app.services.feature_flag_service import feature_flag_service

router = APIRouter(tags=["Dashboard & Relatórios"])


@router.get("/dashboard")
def get_dashboard(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    professional_id: Optional[uuid.UUID] = None,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Professionals only see their own data
    if current_user.role == "professional" and current_user.professional:
        professional_id = current_user.professional.id

    return dashboard_service.get_summary(
        db=db,
        tenant_id=tenant.id,
        date_from=date_from,
        date_to=date_to,
        professional_id=professional_id,
    )


@router.get("/reports/appointments-by-status")
def report_appointments_by_status(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    professional_id: Optional[uuid.UUID] = None,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    feature_flag_service.require_feature(db, tenant, "advanced_reports")

    q = db.query(Appointment.status, func.count(Appointment.id).label("count")).filter(
        Appointment.tenant_id == tenant.id
    )
    if professional_id:
        q = q.filter(Appointment.professional_id == professional_id)
    if date_from:
        from datetime import datetime, timezone
        q = q.filter(Appointment.start_datetime >= datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc))
    if date_to:
        from datetime import datetime, timezone, timedelta
        dt_to = datetime(date_to.year, date_to.month, date_to.day, tzinfo=timezone.utc) + timedelta(days=1)
        q = q.filter(Appointment.start_datetime < dt_to)

    rows = q.group_by(Appointment.status).all()
    return [{"status": r.status, "count": r.count} for r in rows]


@router.get("/reports/revenue-by-professional")
def report_revenue_by_professional(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    feature_flag_service.require_feature(db, tenant, "advanced_reports")

    q = (
        db.query(
            Professional.name,
            func.count(Appointment.id).label("total_appointments"),
            func.sum(Appointment.total_price).label("total_revenue"),
        )
        .join(Appointment, Appointment.professional_id == Professional.id)
        .filter(
            Appointment.tenant_id == tenant.id,
            Appointment.status == "completed",
        )
    )
    if date_from:
        from datetime import datetime, timezone
        q = q.filter(Appointment.start_datetime >= datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc))
    if date_to:
        from datetime import datetime, timezone, timedelta
        dt_to = datetime(date_to.year, date_to.month, date_to.day, tzinfo=timezone.utc) + timedelta(days=1)
        q = q.filter(Appointment.start_datetime < dt_to)

    rows = q.group_by(Professional.id, Professional.name).all()
    return [
        {
            "professional_name": r.name,
            "total_appointments": r.total_appointments,
            "total_revenue": float(r.total_revenue or 0),
        }
        for r in rows
    ]


@router.get("/reports/revenue-by-service")
def report_revenue_by_service(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    feature_flag_service.require_feature(db, tenant, "advanced_reports")

    from app.models.appointment import AppointmentService as AppointmentServiceModel
    q = (
        db.query(
            AppointmentServiceModel.service_name_snapshot.label("service_name"),
            func.count(AppointmentServiceModel.id).label("count"),
            func.sum(AppointmentServiceModel.service_price_snapshot).label("revenue"),
        )
        .join(Appointment, Appointment.id == AppointmentServiceModel.appointment_id)
        .filter(
            AppointmentServiceModel.tenant_id == tenant.id,
            Appointment.status == "completed",
        )
    )
    rows = q.group_by(AppointmentServiceModel.service_name_snapshot).all()
    return [
        {"service_name": r.service_name, "count": r.count, "revenue": float(r.revenue or 0)}
        for r in rows
    ]


@router.get("/reports/new-customers-over-time")
def report_new_customers(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    feature_flag_service.require_feature(db, tenant, "advanced_reports")

    rows = (
        db.query(
            extract("year", TenantCustomer.created_at).label("year"),
            extract("month", TenantCustomer.created_at).label("month"),
            func.count(TenantCustomer.id).label("count"),
        )
        .filter(TenantCustomer.tenant_id == tenant.id)
        .group_by("year", "month")
        .order_by("year", "month")
        .all()
    )
    return [{"year": int(r.year), "month": int(r.month), "count": r.count} for r in rows]


@router.get("/reports/occupancy-rate")
def report_occupancy_rate(
    date_from: date = Query(...),
    date_to: date = Query(...),
    professional_id: Optional[uuid.UUID] = None,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    feature_flag_service.require_feature(db, tenant, "advanced_reports")

    from datetime import datetime, timezone, timedelta
    from app.models.schedule import BusinessHour

    # Count total booked minutes in range
    q = db.query(func.sum(Appointment.total_duration_minutes)).filter(
        Appointment.tenant_id == tenant.id,
        Appointment.status.in_(["scheduled", "confirmed", "completed", "in_progress"]),
        Appointment.start_datetime >= datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc),
        Appointment.start_datetime < datetime(date_to.year, date_to.month, date_to.day, tzinfo=timezone.utc) + timedelta(days=1),
    )
    if professional_id:
        q = q.filter(Appointment.professional_id == professional_id)

    booked_minutes = q.scalar() or 0

    # Approximate available minutes from business hours
    days = (date_to - date_from).days + 1
    bh_avg = db.query(BusinessHour).filter(BusinessHour.tenant_id == tenant.id, BusinessHour.is_closed == False).all()
    avg_minutes = sum(
        (bh.close_time.hour * 60 + bh.close_time.minute) - (bh.open_time.hour * 60 + bh.open_time.minute)
        for bh in bh_avg if bh.open_time and bh.close_time
    )

    # Number of professionals
    n_prof = 1 if professional_id else max(
        db.query(Professional).filter(Professional.tenant_id == tenant.id, Professional.is_active == True).count(), 1
    )
    total_available = avg_minutes * days * n_prof
    occupancy = (booked_minutes / total_available * 100) if total_available > 0 else 0

    return {
        "booked_minutes": booked_minutes,
        "available_minutes": total_available,
        "occupancy_rate_percent": round(occupancy, 2),
    }
