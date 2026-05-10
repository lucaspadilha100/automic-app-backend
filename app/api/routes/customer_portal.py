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
from app.models.future import AppointmentReview
from app.models.product import ProductOrder
from app.services.appointment_service import appointment_service
from app.schemas.auth import CustomerResponse
from app.schemas.schemas import (
    CustomerProfileUpdate, CustomerPortalProfileResponse, AppointmentCancelRequest,
    AppointmentRescheduleRequest, CustomerPortalAppointmentResponse,
    CustomerPortalPackageResponse, CustomerPortalProcedureHistoryResponse,
    ReviewCreate, ReviewResponse,
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


@router.get("/tenants/{slug}/appointments/{appointment_id}/review", response_model=ReviewResponse)
def get_appointment_review(slug: str, appointment_id: uuid.UUID, db: Session = Depends(get_db), current_customer: CustomerAccount = Depends(get_current_customer)):
    tenant = get_public_tenant_by_slug(slug, db)
    review = db.query(AppointmentReview).filter(
        AppointmentReview.appointment_id == appointment_id,
        AppointmentReview.tenant_id == tenant.id,
        AppointmentReview.customer_account_id == current_customer.id,
    ).first()
    if not review:
        raise NotFoundError("REVIEW_NOT_FOUND", "Avaliação não encontrada.")
    return review


@router.post("/tenants/{slug}/appointments/{appointment_id}/review", response_model=ReviewResponse)
def create_appointment_review(slug: str, appointment_id: uuid.UUID, payload: ReviewCreate, db: Session = Depends(get_db), current_customer: CustomerAccount = Depends(get_current_customer)):
    tenant = get_public_tenant_by_slug(slug, db)
    appt = db.query(Appointment).filter(Appointment.id == appointment_id, Appointment.tenant_id == tenant.id, Appointment.customer_account_id == current_customer.id).first()
    if not appt:
        raise NotFoundError("APPOINTMENT_NOT_FOUND", "Agendamento não encontrado.")
    existing = db.query(AppointmentReview).filter(AppointmentReview.appointment_id == appointment_id, AppointmentReview.customer_account_id == current_customer.id).first()
    if existing:
        existing.rating = payload.rating
        existing.comment = payload.comment
        existing.visibility = payload.visibility
        db.commit()
        db.refresh(existing)
        return existing
    review = AppointmentReview(
        tenant_id=tenant.id,
        appointment_id=appointment_id,
        customer_account_id=current_customer.id,
        rating=payload.rating,
        comment=payload.comment,
        visibility=payload.visibility,
        created_at=datetime.now(timezone.utc),
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@router.post("/tenants/{slug}/product-orders")
def customer_create_product_order(slug: str, payload: dict, db: Session = Depends(get_db), current_customer: CustomerAccount = Depends(get_current_customer)):
    from app.models.product import Product
    from decimal import Decimal
    tenant = get_public_tenant_by_slug(slug, db)
    items_data = []
    total = Decimal("0")
    for item in payload.get("items", []):
        product = db.query(Product).filter(Product.id == item["product_id"], Product.tenant_id == tenant.id, Product.is_active == True).first()
        if not product:
            raise NotFoundError("PRODUCT_NOT_FOUND", f"Produto não encontrado.")
        qty = int(item.get("quantity", 1))
        item_total = product.price * qty
        total += item_total
        items_data.append({"product_id": str(product.id), "product_name": product.name, "quantity": qty, "unit_price": float(product.price)})
        if product.track_stock and product.stock_quantity is not None:
            product.stock_quantity -= qty
    order = ProductOrder(
        tenant_id=tenant.id,
        customer_account_id=current_customer.id,
        customer_name=payload.get("customer_name", current_customer.name),
        customer_phone=payload.get("customer_phone"),
        items=items_data,
        total=total,
        notes=payload.get("notes"),
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return {"id": str(order.id), "total": float(order.total), "status": order.status, "items": order.items}
