from typing import Optional
from datetime import datetime, timezone, timedelta
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import get_current_customer, get_public_tenant_by_slug
from app.core.exceptions import NotFoundError, ForbiddenError, InvalidBookingPolicyError
from app.models.customer import CustomerAccount, TenantCustomer
from app.models.appointment import Appointment
from app.models.package import CustomerPackage
from app.models.procedure import ProcedureHistory
from app.models.tenant import TenantBookingPolicy
from app.services.appointment_service import appointment_service
from app.schemas.auth import CustomerResponse
from app.schemas.schemas import (
    CustomerProfileUpdate, CustomerPortalProfileResponse, AppointmentCancelRequest,
    AppointmentRescheduleRequest, CustomerPortalAppointmentResponse,
    CustomerPortalPackageResponse, CustomerPortalProcedureHistoryResponse,
)

router = APIRouter(prefix="/customer", tags=["Portal do Cliente"])


def _tenant_customer(db: Session, tenant_id, customer_id) -> Optional[TenantCustomer]:
    return db.query(TenantCustomer).filter(TenantCustomer.tenant_id == tenant_id, TenantCustomer.customer_account_id == customer_id).first()


@router.get("/me", response_model=CustomerResponse)
def customer_me(current_customer: CustomerAccount = Depends(get_current_customer)):
    return current_customer


@router.put("/me", response_model=CustomerResponse)
def update_customer_me(payload: CustomerProfileUpdate, current_customer: CustomerAccount = Depends(get_current_customer), db: Session = Depends(get_db)):
    data = payload.model_dump(exclude_none=True)
    for field in ("name", "email", "phone"):
        if field in data:
            setattr(current_customer, field, data[field])
    db.commit()
    db.refresh(current_customer)
    return current_customer


@router.get("/tenants/{slug}/profile", response_model=CustomerPortalProfileResponse)
def get_tenant_profile(slug: str, db: Session = Depends(get_db), current_customer: CustomerAccount = Depends(get_current_customer)):
    tenant = get_public_tenant_by_slug(slug, db)
    tc = _tenant_customer(db, tenant.id, current_customer.id)
    return CustomerPortalProfileResponse(
        customer_account_id=current_customer.id,
        tenant_customer_id=tc.id if tc else None,
        name=current_customer.name,
        email=current_customer.email,
        phone=current_customer.phone,
        cpf=tc.cpf if tc else None,
        birth_date=tc.birth_date if tc else None,
        notes=tc.notes if tc else None,
        marketing_consent=tc.marketing_consent if tc else None,
    )


@router.put("/tenants/{slug}/profile", response_model=CustomerPortalProfileResponse)
def update_tenant_profile(slug: str, payload: CustomerProfileUpdate, db: Session = Depends(get_db), current_customer: CustomerAccount = Depends(get_current_customer)):
    tenant = get_public_tenant_by_slug(slug, db)
    tc = _tenant_customer(db, tenant.id, current_customer.id)
    if not tc:
        tc = TenantCustomer(tenant_id=tenant.id, customer_account_id=current_customer.id)
        db.add(tc)
        db.flush()
    data = payload.model_dump(exclude_none=True)
    for field in ("name", "email", "phone"):
        if field in data:
            setattr(current_customer, field, data[field])
    for field in ("cpf", "birth_date", "notes", "marketing_consent"):
        if field in data:
            setattr(tc, field, data[field])
    db.commit()
    return get_tenant_profile(slug, db, current_customer)


@router.get("/tenants/{slug}/appointments", response_model=list[CustomerPortalAppointmentResponse])
def list_customer_appointments(slug: str, db: Session = Depends(get_db), current_customer: CustomerAccount = Depends(get_current_customer)):
    tenant = get_public_tenant_by_slug(slug, db)
    return db.query(Appointment).filter(Appointment.tenant_id == tenant.id, Appointment.customer_account_id == current_customer.id).order_by(Appointment.start_datetime.desc()).all()


@router.get("/tenants/{slug}/appointments/{appointment_id}", response_model=CustomerPortalAppointmentResponse)
def get_customer_appointment(slug: str, appointment_id: uuid.UUID, db: Session = Depends(get_db), current_customer: CustomerAccount = Depends(get_current_customer)):
    tenant = get_public_tenant_by_slug(slug, db)
    appt = db.query(Appointment).filter(Appointment.id == appointment_id, Appointment.tenant_id == tenant.id, Appointment.customer_account_id == current_customer.id).first()
    if not appt:
        raise NotFoundError("APPOINTMENT_NOT_FOUND", "Agendamento não encontrado.")
    return appt


@router.post("/tenants/{slug}/appointments/{appointment_id}/cancel")
def cancel_customer_appointment(slug: str, appointment_id: uuid.UUID, payload: AppointmentCancelRequest, db: Session = Depends(get_db), current_customer: CustomerAccount = Depends(get_current_customer)):
    tenant = get_public_tenant_by_slug(slug, db)
    appt = db.query(Appointment).filter(Appointment.id == appointment_id, Appointment.tenant_id == tenant.id, Appointment.customer_account_id == current_customer.id).first()
    if not appt:
        raise NotFoundError("APPOINTMENT_NOT_FOUND", "Agendamento não encontrado.")
    policy = db.query(TenantBookingPolicy).filter(TenantBookingPolicy.tenant_id == tenant.id).first()
    if policy and not policy.allow_customer_cancel:
        raise InvalidBookingPolicyError("Cancelamento pelo cliente não está habilitado.")
    if policy and policy.min_hours_before_cancel:
        if appt.start_datetime < datetime.now(timezone.utc) + timedelta(hours=policy.min_hours_before_cancel):
            raise InvalidBookingPolicyError("Cancelamento fora do prazo permitido.")
    appointment_service.cancel(db, appt, "customer", current_customer.id, payload.reason)
    db.commit()
    return {"message": "Agendamento cancelado."}


@router.post("/tenants/{slug}/appointments/{appointment_id}/reschedule", response_model=CustomerPortalAppointmentResponse)
def reschedule_customer_appointment(slug: str, appointment_id: uuid.UUID, payload: AppointmentRescheduleRequest, db: Session = Depends(get_db), current_customer: CustomerAccount = Depends(get_current_customer)):
    tenant = get_public_tenant_by_slug(slug, db)
    appt = db.query(Appointment).filter(Appointment.id == appointment_id, Appointment.tenant_id == tenant.id, Appointment.customer_account_id == current_customer.id).first()
    if not appt:
        raise NotFoundError("APPOINTMENT_NOT_FOUND", "Agendamento não encontrado.")
    policy = db.query(TenantBookingPolicy).filter(TenantBookingPolicy.tenant_id == tenant.id).first()
    if policy and not policy.allow_customer_reschedule:
        raise InvalidBookingPolicyError("Reagendamento pelo cliente não está habilitado.")
    if policy and policy.min_hours_before_reschedule:
        if appt.start_datetime < datetime.now(timezone.utc) + timedelta(hours=policy.min_hours_before_reschedule):
            raise InvalidBookingPolicyError("Reagendamento fora do prazo permitido.")
    service_ids = [svc.service_id for svc in appt.appointment_services if svc.service_id]
    appointment_service.cancel(db, appt, "customer", current_customer.id, payload.reason or "Reagendado")
    new_appt = appointment_service.create(db, tenant, appt.professional_id, service_ids, payload.new_start_datetime, current_customer.id, appt.tenant_customer_id, appt.customer_notes, None, "public_page", customer_package_id=appt.customer_package_id)
    appt.status = "rescheduled"
    db.commit()
    return new_appt


@router.get("/tenants/{slug}/packages", response_model=list[CustomerPortalPackageResponse])
def list_customer_packages(slug: str, db: Session = Depends(get_db), current_customer: CustomerAccount = Depends(get_current_customer)):
    tenant = get_public_tenant_by_slug(slug, db)
    return db.query(CustomerPackage).filter(CustomerPackage.tenant_id == tenant.id, CustomerPackage.customer_account_id == current_customer.id).all()


@router.get("/tenants/{slug}/packages/{customer_package_id}", response_model=CustomerPortalPackageResponse)
def get_customer_package(slug: str, customer_package_id: uuid.UUID, db: Session = Depends(get_db), current_customer: CustomerAccount = Depends(get_current_customer)):
    tenant = get_public_tenant_by_slug(slug, db)
    cp = db.query(CustomerPackage).filter(CustomerPackage.id == customer_package_id, CustomerPackage.tenant_id == tenant.id, CustomerPackage.customer_account_id == current_customer.id).first()
    if not cp:
        raise NotFoundError("CUSTOMER_PACKAGE_NOT_FOUND", "Pacote não encontrado.")
    return cp


@router.get("/tenants/{slug}/procedure-history", response_model=list[CustomerPortalProcedureHistoryResponse])
def list_customer_procedure_history(slug: str, db: Session = Depends(get_db), current_customer: CustomerAccount = Depends(get_current_customer)):
    tenant = get_public_tenant_by_slug(slug, db)
    return db.query(ProcedureHistory).filter(ProcedureHistory.tenant_id == tenant.id, ProcedureHistory.customer_account_id == current_customer.id).order_by(ProcedureHistory.procedure_date.desc()).all()
