from typing import List, Optional
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import uuid

from db.session import get_db
from app.core.dependencies import (
    get_current_user, require_active_tenant, require_receptionist_or_above,
)
from app.core.exceptions import NotFoundError, ForbiddenError
from app.models.user import User
from app.models.tenant import Tenant
from app.models.appointment import Appointment
from app.models.customer import TenantCustomer
from app.services.appointment_service import appointment_service
from app.services.audit_service import audit_service
from app.schemas.schemas import (
    AppointmentCreate, AppointmentResponse,
    AppointmentCancelRequest, AppointmentRescheduleRequest,
)

router = APIRouter(prefix="/appointments", tags=["Agendamentos"])

VALID_STATUS_TRANSITIONS = {
    "scheduled": ["confirmed", "cancelled", "in_progress", "no_show"],
    "confirmed": ["in_progress", "cancelled", "no_show"],
    "in_progress": ["completed", "cancelled", "no_show"],
    "pending_payment": ["scheduled", "cancelled"],
}


def _get_appointment(appointment_id: uuid.UUID, tenant: Tenant, db: Session) -> Appointment:
    appt = db.query(Appointment).filter(
        Appointment.id == appointment_id, Appointment.tenant_id == tenant.id
    ).first()
    if not appt:
        raise NotFoundError("APPOINTMENT_NOT_FOUND", "Agendamento não encontrado.")
    return appt


@router.post("", response_model=AppointmentResponse)
def create_appointment(
    payload: AppointmentCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    # Resolve tenant_customer_id from customer_account_id if provided
    tenant_customer_id = None
    if payload.customer_account_id:
        tc = db.query(TenantCustomer).filter(
            TenantCustomer.tenant_id == tenant.id,
            TenantCustomer.customer_account_id == payload.customer_account_id,
        ).first()
        if tc:
            tenant_customer_id = tc.id

    appt = appointment_service.create(
        db=db,
        tenant=tenant,
        professional_id=payload.professional_id,
        service_ids=payload.service_ids,
        start_datetime=payload.start_datetime,
        customer_account_id=payload.customer_account_id,
        tenant_customer_id=tenant_customer_id,
        customer_notes=payload.customer_notes,
        internal_notes=payload.internal_notes,
        source=payload.source,
        idempotency_key=payload.idempotency_key,
        customer_package_id=payload.customer_package_id,
        created_by_user_id=current_user.id,
        unit_id=payload.unit_id,
    )
    db.commit()
    db.refresh(appt)
    return appt


@router.get("", response_model=List[AppointmentResponse])
def list_appointments(
    status: Optional[str] = None,
    professional_id: Optional[uuid.UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    customer_account_id: Optional[uuid.UUID] = None,
    skip: int = 0,
    limit: int = Query(50, le=200),
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Appointment).filter(Appointment.tenant_id == tenant.id)

    # Professional role can only see their own
    if current_user.role == "professional":
        if current_user.professional:
            q = q.filter(Appointment.professional_id == current_user.professional.id)
        else:
            return []

    if status:
        q = q.filter(Appointment.status == status)
    if professional_id:
        q = q.filter(Appointment.professional_id == professional_id)
    if customer_account_id:
        q = q.filter(Appointment.customer_account_id == customer_account_id)
    if date_from:
        q = q.filter(Appointment.start_datetime >= datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc))
    if date_to:
        from datetime import timedelta
        dt_to = datetime(date_to.year, date_to.month, date_to.day, tzinfo=timezone.utc) + timedelta(days=1)
        q = q.filter(Appointment.start_datetime < dt_to)

    return q.order_by(Appointment.start_datetime).offset(skip).limit(limit).all()


@router.get("/{appointment_id}", response_model=AppointmentResponse)
def get_appointment(
    appointment_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    appt = _get_appointment(appointment_id, tenant, db)
    if current_user.role == "professional" and current_user.professional:
        if str(appt.professional_id) != str(current_user.professional.id):
            raise ForbiddenError()
    return appt


@router.post("/{appointment_id}/confirm", response_model=AppointmentResponse)
def confirm_appointment(
    appointment_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    appt = _get_appointment(appointment_id, tenant, db)
    appt = appointment_service.confirm(db, appt, current_user.id)
    db.commit()
    db.refresh(appt)
    return appt


@router.post("/{appointment_id}/start", response_model=AppointmentResponse)
def start_appointment(
    appointment_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    appt = _get_appointment(appointment_id, tenant, db)
    appt = appointment_service.start(db, appt, current_user.id)
    db.commit()
    db.refresh(appt)
    return appt


@router.post("/{appointment_id}/complete", response_model=AppointmentResponse)
def complete_appointment(
    appointment_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    appt = _get_appointment(appointment_id, tenant, db)
    appt = appointment_service.complete(db, appt, current_user.id)
    db.commit()
    db.refresh(appt)
    return appt


@router.post("/{appointment_id}/cancel", response_model=AppointmentResponse)
def cancel_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentCancelRequest,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    appt = _get_appointment(appointment_id, tenant, db)
    appt = appointment_service.cancel(
        db, appt, "user", current_user.id, payload.reason
    )
    db.commit()
    db.refresh(appt)
    return appt


@router.post("/{appointment_id}/no-show", response_model=AppointmentResponse)
def no_show_appointment(
    appointment_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    appt = _get_appointment(appointment_id, tenant, db)
    appt = appointment_service.no_show(db, appt, current_user.id)
    db.commit()
    db.refresh(appt)
    return appt


@router.post("/{appointment_id}/reschedule", response_model=AppointmentResponse)
def reschedule_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentRescheduleRequest,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    """
    Reschedule an existing appointment to a new datetime.

    Atomic flow:
      1. Validate old appointment is in a reschedulable state
      2. Create the NEW appointment first (will check schedule exceptions
         + service availability automatically via appointment_service.create)
      3. If creation succeeds, mark old as 'rescheduled' and link the chain
      4. If anything fails, the new appointment is rolled back and the old
         remains untouched (no orphan)
    """
    old_appt = _get_appointment(appointment_id, tenant, db)

    # Block reschedule of already-cancelled / completed / rescheduled appointments
    if old_appt.status in ("cancelled", "completed", "no_show", "rescheduled"):
        from app.core.exceptions import ConflictError
        raise ConflictError(
            code="APPOINTMENT_NOT_RESCHEDULABLE",
            message=(
                f"Agendamento com status '{old_appt.status}' não pode ser remarcado. "
                "Crie um novo agendamento."
            ),
        )

    service_ids = [svc.service_id for svc in old_appt.appointment_services if svc.service_id]

    try:
        # 1) Create the new appointment FIRST. This validates exceptions,
        #    professional availability, package usage etc — and raises before
        #    we touch the old appointment if anything goes wrong.
        new_appt = appointment_service.create(
            db=db,
            tenant=tenant,
            professional_id=old_appt.professional_id,
            service_ids=service_ids,
            start_datetime=payload.new_start_datetime,
            customer_account_id=old_appt.customer_account_id,
            tenant_customer_id=old_appt.tenant_customer_id,
            internal_notes=old_appt.internal_notes,
            customer_notes=old_appt.customer_notes,
            source=old_appt.source,
            customer_package_id=old_appt.customer_package_id,
            created_by_user_id=current_user.id,
            unit_id=old_appt.unit_id,
        )

        # 2) Link the chain and cancel the old one
        new_appt.rescheduled_from_id = old_appt.id
        old_appt.rescheduled_to_id = new_appt.id
        # Mark cancelled so the slot is freed; status='rescheduled' kept for trail
        appointment_service.cancel(
            db, old_appt, "user", current_user.id,
            payload.reason or "Remarcado",
        )
        old_appt.status = "rescheduled"  # overwrite — cancelled would lose the chain meaning
        db.add(old_appt)
        db.add(new_appt)
        db.commit()
        db.refresh(new_appt)
        return new_appt
    except Exception:
        db.rollback()
        raise


@router.get("/{appointment_id}/status-history")
def get_status_history(
    appointment_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    appt = _get_appointment(appointment_id, tenant, db)
    return appt.status_history
