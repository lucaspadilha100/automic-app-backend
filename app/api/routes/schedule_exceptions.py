"""
Routes for managing ScheduleExceptions (tenant operator).

Endpoints:
  GET    /schedule-exceptions               — list (with filters)
  POST   /schedule-exceptions               — create
  GET    /schedule-exceptions/{id}          — detail
  PATCH  /schedule-exceptions/{id}          — update
  DELETE /schedule-exceptions/{id}          — remove

Plus the bulk-cancel endpoint at:
  POST   /appointments/bulk-cancel          — cancel everything in a window
                                               (used when a professional needs
                                               to call out for the whole day)
"""
from typing import List, Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import (
    require_active_tenant, require_receptionist_or_above, require_manager_or_above,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.models.appointment import Appointment
from app.schemas.schedule_exception import (
    ScheduleExceptionCreate, ScheduleExceptionUpdate, ScheduleExceptionResponse,
    BulkCancelRequest, BulkCancelResponse,
)
from app.services.schedule_exception_service import schedule_exception_service
from app.services.appointment_service import appointment_service

router = APIRouter(
    prefix="/schedule-exceptions",
    tags=["Schedule Exceptions"],
)


@router.get("", response_model=List[ScheduleExceptionResponse])
def list_exceptions(
    professional_id: Optional[uuid.UUID] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    return schedule_exception_service.list_for_tenant(
        db, tenant.id,
        professional_id=professional_id,
        from_dt=from_date, to_dt=to_date,
    )


@router.post("", response_model=ScheduleExceptionResponse, status_code=201)
def create_exception(
    payload: ScheduleExceptionCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    return schedule_exception_service.create(
        db, tenant.id, payload.model_dump(),
        created_by_user_id=current_user.id,
    )


@router.get("/{exception_id}", response_model=ScheduleExceptionResponse)
def get_exception(
    exception_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    return schedule_exception_service.get(db, tenant.id, exception_id)


@router.patch("/{exception_id}", response_model=ScheduleExceptionResponse)
def update_exception(
    exception_id: uuid.UUID,
    payload: ScheduleExceptionUpdate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    exc = schedule_exception_service.get(db, tenant.id, exception_id)
    return schedule_exception_service.update(
        db, exc, payload.model_dump(exclude_unset=True),
    )


@router.delete("/{exception_id}", status_code=204)
def delete_exception(
    exception_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    exc = schedule_exception_service.get(db, tenant.id, exception_id)
    schedule_exception_service.delete(db, exc)
    return None


# ── Bulk cancel ──────────────────────────────────────────────────────────────
# Lives here (vs appointments router) because it pairs naturally with creating
# a leave/closure exception — the typical flow is "doctor called in sick →
# (1) create leave exception (2) bulk-cancel existing appointments in that window".

bulk_router = APIRouter(prefix="/appointments", tags=["Appointments"])


@bulk_router.post("/bulk-cancel", response_model=BulkCancelResponse)
def bulk_cancel_appointments(
    payload: BulkCancelRequest,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    """
    Cancel all active appointments for one professional within a window.

    Useful when:
      - Professional calls out sick and you need to reach all clients
      - Clinic closes due to power outage / event
      - You're also creating a ScheduleException for the same window

    Skips appointments already in terminal states (cancelled/completed/no_show/rescheduled).
    Returns the IDs cancelled so the frontend can drive customer notifications.
    """
    appts = (
        db.query(Appointment)
        .filter(
            Appointment.tenant_id == tenant.id,
            Appointment.professional_id == payload.professional_id,
            Appointment.start_datetime >= payload.start_datetime,
            Appointment.start_datetime < payload.end_datetime,
            Appointment.status.in_(("scheduled", "confirmed", "pending_payment")),
        )
        .all()
    )

    cancelled_ids: List[uuid.UUID] = []
    notified = 0

    for appt in appts:
        try:
            appointment_service.cancel(
                db, appt, "user", current_user.id, payload.reason,
            )
            cancelled_ids.append(appt.id)
        except Exception:
            continue

    db.commit()

    # Best-effort customer notifications
    if payload.notify_customers and cancelled_ids:
        from app.services.notification_service import notification_service
        for appt in appts:
            if appt.id not in cancelled_ids:
                continue
            customer = appt.customer_account
            if not customer:
                continue
            ctx = {
                "customer_name": customer.name or "",
                "tenant_name": (tenant.public_name or tenant.name),
                "appointment_date": appt.start_datetime.strftime("%d/%m/%Y %H:%M"),
                "reason": payload.reason,
            }
            try:
                if customer.phone:
                    notification_service.send_generic(
                        db, tenant_id=tenant.id, channel="whatsapp",
                        event_type="appointment_cancelled_bulk",
                        to=customer.phone, context=ctx,
                        appointment_id=appt.id,
                        customer_account_id=customer.id,
                    )
                    notified += 1
                elif customer.email:
                    notification_service.send_generic(
                        db, tenant_id=tenant.id, channel="email",
                        event_type="appointment_cancelled_bulk",
                        to=customer.email, context=ctx,
                        appointment_id=appt.id,
                        customer_account_id=customer.id,
                    )
                    notified += 1
            except Exception:
                continue

    return BulkCancelResponse(
        cancelled_count=len(cancelled_ids),
        notified_count=notified,
        appointment_ids=cancelled_ids,
    )
