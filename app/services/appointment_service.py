import hashlib, json
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.appointment import (
    Appointment,
    AppointmentService as AppointmentServiceModel,
    AppointmentStatusHistory,
    IdempotencyKey,
)
from app.models.professional import Professional
from app.models.service import Service
from app.models.customer import TenantCustomer, CustomerAccount
from app.models.procedure import ProcedureHistory
from app.models.tenant import Tenant, TenantBookingPolicy

from app.services.availability_service import availability_service
from app.services.audit_service import audit_service
from app.services.customer_event_service import customer_event_service
from app.services.package_service import package_service

from app.core.exceptions import (
    AppointmentConflictError, InvalidAvailabilityError,
    ServiceNotFoundError, ProfessionalNotFoundError,
    CustomerNotFoundError, AppError
)


class AppointmentService:

    def _record_status_history(
        self, db: Session, appointment: Appointment,
        from_status: Optional[str], to_status: str,
        changed_by_type: str, changed_by_id: Optional[UUID],
        reason: Optional[str] = None,
    ):
        h = AppointmentStatusHistory(
            tenant_id=appointment.tenant_id,
            appointment_id=appointment.id,
            from_status=from_status,
            to_status=to_status,
            old_status=from_status,
            new_status=to_status,
            changed_by_type=changed_by_type,
            changed_by_id=changed_by_id,
            changed_by_user_id=changed_by_id if changed_by_type == "user" else None,
            changed_by_customer_id=changed_by_id if changed_by_type == "customer" else None,
            reason=reason,
            created_at=datetime.now(timezone.utc),
        )
        db.add(h)

    def _check_idempotency(
        self, db: Session, tenant_id: UUID,
        customer_account_id: Optional[UUID], idempotency_key: Optional[str],
        payload: dict,
    ) -> Optional[Appointment]:
        if not idempotency_key:
            return None
        req_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        existing = (
            db.query(IdempotencyKey)
            .filter(
                IdempotencyKey.tenant_id == tenant_id,
                IdempotencyKey.key == idempotency_key,
            )
            .first()
        )
        if existing:
            if existing.request_hash == req_hash and existing.response_body:
                # Return stored response signal
                appt_id = existing.response_body.get("appointment_id")
                if appt_id:
                    return db.query(Appointment).filter(Appointment.id == appt_id).first()
            elif existing.status == "processing":
                raise AppointmentConflictError()
        else:
            idem = IdempotencyKey(
                tenant_id=tenant_id,
                customer_account_id=customer_account_id,
                key=idempotency_key,
                request_hash=req_hash,
                status="processing",
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            )
            db.add(idem)
            db.flush()
        return None

    def _mark_idempotency_done(
        self, db: Session, tenant_id: UUID, key: str, appointment_id: UUID
    ):
        idem = (
            db.query(IdempotencyKey)
            .filter(IdempotencyKey.tenant_id == tenant_id, IdempotencyKey.key == key)
            .first()
        )
        if idem:
            idem.status = "completed"
            idem.response_body = {"appointment_id": str(appointment_id)}

    def create(
        self,
        db: Session,
        tenant: Tenant,
        professional_id: UUID,
        service_ids: List[UUID],
        start_datetime: datetime,
        customer_account_id: Optional[UUID] = None,
        tenant_customer_id: Optional[UUID] = None,
        customer_notes: Optional[str] = None,
        internal_notes: Optional[str] = None,
        source: str = "admin_panel",
        idempotency_key: Optional[str] = None,
        customer_package_id: Optional[UUID] = None,
        created_by_user_id: Optional[UUID] = None,
        unit_id: Optional[UUID] = None,
    ) -> Appointment:

        # Idempotency check
        payload = {
            "professional_id": str(professional_id),
            "service_ids": [str(s) for s in service_ids],
            "start_datetime": start_datetime.isoformat(),
        }
        existing = self._check_idempotency(db, tenant.id, customer_account_id, idempotency_key, payload)
        if existing:
            return existing

        # Load services
        services = (
            db.query(Service)
            .filter(Service.id.in_(service_ids), Service.tenant_id == tenant.id, Service.is_active == True)
            .all()
        )
        if len(services) != len(service_ids):
            raise ServiceNotFoundError()

        # Load professional
        professional = (
            db.query(Professional)
            .filter(Professional.id == professional_id, Professional.tenant_id == tenant.id, Professional.is_active == True)
            .first()
        )
        if not professional:
            raise ProfessionalNotFoundError()

        # Validate professional can perform services
        prof_service_ids = {str(ps.service_id) for ps in professional.professional_services}
        for sid in service_ids:
            if str(sid) not in prof_service_ids:
                raise InvalidAvailabilityError(f"O profissional não realiza o serviço solicitado.")

        # Calculate duration
        total_duration = sum(s.duration_minutes for s in services)
        buffer_before = max((s.buffer_before_minutes for s in services), default=0)
        buffer_after = max((s.buffer_after_minutes for s in services), default=0)
        effective_duration = buffer_before + total_duration + buffer_after

        # Ensure UTC
        if start_datetime.tzinfo is None:
            import pytz
            tz = pytz.timezone(tenant.timezone)
            start_datetime = tz.localize(start_datetime).astimezone(pytz.utc)

        end_datetime = start_datetime + timedelta(minutes=effective_duration)
        total_price = sum(s.price for s in services)

        # Block if a ScheduleException covers this slot (holiday, leave, closure)
        from app.services.schedule_exception_service import schedule_exception_service
        from app.core.exceptions import ConflictError
        blocking = schedule_exception_service.find_blocking(
            db=db, tenant_id=tenant.id,
            professional_id=professional_id,
            start_dt=start_datetime, end_dt=end_datetime,
            unit_id=unit_id,
        )
        if blocking:
            raise ConflictError(
                code="SCHEDULE_BLOCKED",
                message=(
                    f"Horário bloqueado por {blocking.exception_type}"
                    + (f": {blocking.reason}" if blocking.reason else ".")
                ),
            )

        # Package validation
        if customer_package_id:
            package_service.validate_package_use(
                db=db, tenant=tenant,
                customer_package_id=customer_package_id,
                service_ids=service_ids,
            )

        # Concurrency-safe availability check (SELECT FOR UPDATE)
        availability_service.validate_slot(db, tenant, professional_id, start_datetime, end_datetime)

        # Create appointment
        appt = Appointment(
            tenant_id=tenant.id,
            tenant_customer_id=tenant_customer_id,
            customer_account_id=customer_account_id,
            professional_id=professional_id,
            unit_id=unit_id,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            total_duration_minutes=effective_duration,
            total_price=total_price,
            status="scheduled",
            payment_status="not_required",
            source=source,
            customer_notes=customer_notes,
            internal_notes=internal_notes,
            customer_package_id=customer_package_id,
            uses_package=bool(customer_package_id),
        )
        db.add(appt)
        db.flush()

        package_session = None
        if customer_package_id:
            package_session = package_service.reserve_session(
                db=db, tenant_id=tenant.id,
                customer_package_id=customer_package_id,
                appointment_id=appt.id,
                service_id=service_ids[0] if service_ids else None,
            )

        # Create service snapshots
        for idx, svc in enumerate(services):
            appt_svc = AppointmentServiceModel(
                tenant_id=tenant.id,
                appointment_id=appt.id,
                service_id=svc.id,
                package_session_id=package_session.id if package_session and idx == 0 else None,
                service_name_snapshot=svc.name,
                service_price_snapshot=svc.price,
                service_duration_snapshot=svc.duration_minutes,
                created_at=datetime.now(timezone.utc),
            )
            db.add(appt_svc)

        # Status history
        self._record_status_history(db, appt, None, "scheduled", "user" if created_by_user_id else "system", created_by_user_id)

        # Audit log
        audit_service.log(
            db=db, action="appointment_created",
            entity_type="appointment", entity_id=appt.id,
            tenant_id=tenant.id, user_id=created_by_user_id,
            customer_account_id=customer_account_id,
        )

        # CRM event
        customer_event_service.emit(
            db=db, event_type="appointment_created",
            tenant_id=tenant.id,
            customer_account_id=customer_account_id,
            tenant_customer_id=tenant_customer_id,
            entity_type="appointment", entity_id=appt.id,
        )

        # Idempotency mark
        if idempotency_key:
            self._mark_idempotency_done(db, tenant.id, idempotency_key, appt.id)

        # Lifecycle hook
        from app.services.customer_lifecycle_service import customer_lifecycle_service
        customer_lifecycle_service.register_appointment_created(db, appt)

        return appt

    def confirm(self, db: Session, appointment: Appointment, user_id: Optional[UUID] = None) -> Appointment:
        old = appointment.status
        appointment.status = "confirmed"
        appointment.confirmed_at = datetime.now(timezone.utc)
        self._record_status_history(db, appointment, old, "confirmed", "user", user_id)
        audit_service.log(db, "appointment_confirmed", "appointment", appointment.id, appointment.tenant_id, user_id)
        customer_event_service.emit(db, "appointment_confirmed", appointment.tenant_id, appointment.customer_account_id, appointment.tenant_customer_id, "appointment", appointment.id)
        return appointment

    def cancel(
        self, db: Session, appointment: Appointment,
        cancelled_by_type: str, cancelled_by_id: Optional[UUID],
        reason: Optional[str] = None,
    ) -> Appointment:
        old = appointment.status
        appointment.status = "cancelled"
        appointment.cancelled_at = datetime.now(timezone.utc)
        appointment.cancelled_by_type = cancelled_by_type
        appointment.cancelled_by_id = cancelled_by_id
        appointment.cancellation_reason = reason

        # Return package session if reserved
        if appointment.customer_package_id:
            package_service.return_session(db, appointment.tenant_id, appointment.customer_package_id, appointment.id)

        self._record_status_history(db, appointment, old, "cancelled", cancelled_by_type, cancelled_by_id, reason)
        audit_service.log(db, "appointment_cancelled", "appointment", appointment.id, appointment.tenant_id,
                          cancelled_by_id if cancelled_by_type == "user" else None,
                          customer_account_id=cancelled_by_id if cancelled_by_type == "customer" else None)
        customer_event_service.emit(db, "appointment_cancelled", appointment.tenant_id, appointment.customer_account_id, appointment.tenant_customer_id, "appointment", appointment.id)

        # Lifecycle hook
        from app.services.customer_lifecycle_service import customer_lifecycle_service
        customer_lifecycle_service.register_appointment_cancelled(db, appointment)

        return appointment

    def complete(
        self, db: Session, appointment: Appointment, user_id: Optional[UUID] = None
    ) -> Appointment:
        old = appointment.status
        appointment.status = "completed"
        appointment.completed_at = datetime.now(timezone.utc)
        self._record_status_history(db, appointment, old, "completed", "user", user_id)

        # Consume package session
        if appointment.customer_package_id:
            package_service.consume_session(db, appointment.tenant_id, appointment.customer_package_id, appointment.id)

        # Auto-generate procedure history
        ph = ProcedureHistory(
            tenant_id=appointment.tenant_id,
            tenant_customer_id=appointment.tenant_customer_id,
            customer_account_id=appointment.customer_account_id,
            appointment_id=appointment.id,
            professional_id=appointment.professional_id,
            title=", ".join(
                svc.service_name_snapshot for svc in appointment.appointment_services
            ),
            procedure_date=appointment.completed_at,
            created_by_user_id=user_id,
        )
        db.add(ph)

        audit_service.log(db, "appointment_completed", "appointment", appointment.id, appointment.tenant_id, user_id)
        customer_event_service.emit(db, "appointment_completed", appointment.tenant_id, appointment.customer_account_id, appointment.tenant_customer_id, "appointment", appointment.id)

        # Auto-generate commission record — lazy import to avoid circular deps
        from app.services.commission_service import commission_service
        commission_service.generate_for_appointment(db, appointment)

        # Lifecycle hook
        from app.services.customer_lifecycle_service import customer_lifecycle_service
        customer_lifecycle_service.register_appointment_completed(db, appointment)

        return appointment

    def no_show(
        self, db: Session, appointment: Appointment, user_id: Optional[UUID] = None
    ) -> Appointment:
        old = appointment.status
        appointment.status = "no_show"
        appointment.no_show_at = datetime.now(timezone.utc)

        # Package no-show policy: consume or return a reserved session according to tenant settings.
        if appointment.customer_package_id:
            policy = db.query(TenantBookingPolicy).filter(
                TenantBookingPolicy.tenant_id == appointment.tenant_id
            ).first()
            if policy and policy.consume_package_session_on_no_show:
                package_service.consume_session(db, appointment.tenant_id, appointment.customer_package_id, appointment.id)
            else:
                package_service.return_session(db, appointment.tenant_id, appointment.customer_package_id, appointment.id)

        self._record_status_history(db, appointment, old, "no_show", "user", user_id)
        audit_service.log(db, "appointment_no_show", "appointment", appointment.id, appointment.tenant_id, user_id)
        customer_event_service.emit(db, "appointment_no_show", appointment.tenant_id, appointment.customer_account_id, appointment.tenant_customer_id, "appointment", appointment.id)

        # Lifecycle hook
        from app.services.customer_lifecycle_service import customer_lifecycle_service
        customer_lifecycle_service.register_appointment_no_show(db, appointment)

        return appointment

    def start(
        self, db: Session, appointment: Appointment, user_id: Optional[UUID] = None
    ) -> Appointment:
        old = appointment.status
        appointment.status = "in_progress"
        self._record_status_history(db, appointment, old, "in_progress", "user", user_id)
        return appointment


appointment_service = AppointmentService()
