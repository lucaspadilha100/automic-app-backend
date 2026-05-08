from datetime import datetime, timezone
from typing import List
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import require_active_tenant, require_manager_or_above, get_current_user, get_current_customer
from app.core.exceptions import NotFoundError, ForbiddenError, ValidationError
from app.models.tenant import Tenant
from app.models.user import User
from app.models.appointment import Appointment
from app.models.future import AppointmentReview, Coupon, AppointmentHold
from app.models.customer import CustomerAccount
from app.services.audit_service import audit_service
from app.schemas.schemas import (
    ReviewCreate, ReviewResponse, CouponCreate, CouponUpdate, CouponResponse,
    AppointmentHoldCreate, AppointmentHoldResponse,
)

router = APIRouter(tags=["Avaliações, Cupons e Reservas Temporárias"])


@router.get("/reviews", response_model=List[ReviewResponse])
def list_reviews(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(AppointmentReview).filter(AppointmentReview.tenant_id == tenant.id).order_by(AppointmentReview.created_at.desc()).all()


@router.get("/appointments/{appointment_id}/reviews", response_model=List[ReviewResponse])
def list_appointment_reviews(
    appointment_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id, Appointment.tenant_id == tenant.id).first()
    if not appt:
        raise NotFoundError("APPOINTMENT_NOT_FOUND", "Agendamento não encontrado.")
    return db.query(AppointmentReview).filter(AppointmentReview.tenant_id == tenant.id, AppointmentReview.appointment_id == appointment_id).all()


@router.post("/appointments/{appointment_id}/reviews", response_model=ReviewResponse)
def create_appointment_review(
    appointment_id: uuid.UUID,
    payload: ReviewCreate,
    current_customer: CustomerAccount = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    if payload.rating < 1 or payload.rating > 5:
        raise ValidationError("rating deve estar entre 1 e 5.")
    appt = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.customer_account_id == current_customer.id,
    ).first()
    if not appt:
        raise NotFoundError("APPOINTMENT_NOT_FOUND", "Agendamento não encontrado.")
    review = AppointmentReview(
        tenant_id=appt.tenant_id,
        appointment_id=appointment_id,
        customer_account_id=current_customer.id,
        rating=payload.rating,
        comment=payload.comment,
        visibility=payload.visibility,
        created_at=datetime.now(timezone.utc),
    )
    db.add(review)
    db.flush()
    audit_service.log(db, "appointment_review_created", "appointment_review", review.id, appt.tenant_id, customer_account_id=current_customer.id)
    db.commit()
    db.refresh(review)
    return review


@router.get("/coupons", response_model=List[CouponResponse])
def list_coupons(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return db.query(Coupon).filter(Coupon.tenant_id == tenant.id).order_by(Coupon.code).all()


@router.post("/coupons", response_model=CouponResponse)
def create_coupon(
    payload: CouponCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    if payload.discount_value < 0:
        raise ValidationError("discount_value não pode ser negativo.")
    if payload.discount_type == "percentage" and payload.discount_value > 100:
        raise ValidationError("Percentual deve ser até 100.")
    coupon = Coupon(tenant_id=tenant.id, **payload.model_dump())
    db.add(coupon)
    db.flush()
    audit_service.log(db, "coupon_created", "coupon", coupon.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(coupon)
    return coupon


@router.get("/coupons/{coupon_id}", response_model=CouponResponse)
def get_coupon(coupon_id: uuid.UUID, tenant: Tenant = Depends(require_active_tenant), current_user: User = Depends(require_manager_or_above), db: Session = Depends(get_db)):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id, Coupon.tenant_id == tenant.id).first()
    if not coupon:
        raise NotFoundError("COUPON_NOT_FOUND", "Cupom não encontrado.")
    return coupon


@router.put("/coupons/{coupon_id}", response_model=CouponResponse)
def update_coupon(coupon_id: uuid.UUID, payload: CouponUpdate, tenant: Tenant = Depends(require_active_tenant), current_user: User = Depends(require_manager_or_above), db: Session = Depends(get_db)):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id, Coupon.tenant_id == tenant.id).first()
    if not coupon:
        raise NotFoundError("COUPON_NOT_FOUND", "Cupom não encontrado.")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(coupon, k, v)
    audit_service.log(db, "coupon_updated", "coupon", coupon.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(coupon)
    return coupon


@router.patch("/coupons/{coupon_id}/status")
def set_coupon_status(coupon_id: uuid.UUID, is_active: bool = Query(...), tenant: Tenant = Depends(require_active_tenant), current_user: User = Depends(require_manager_or_above), db: Session = Depends(get_db)):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id, Coupon.tenant_id == tenant.id).first()
    if not coupon:
        raise NotFoundError("COUPON_NOT_FOUND", "Cupom não encontrado.")
    coupon.is_active = is_active
    audit_service.log(db, "coupon_status_updated", "coupon", coupon.id, tenant.id, current_user.id)
    db.commit()
    return {"is_active": coupon.is_active}


@router.post("/appointment-holds", response_model=AppointmentHoldResponse)
def create_hold(payload: AppointmentHoldCreate, tenant: Tenant = Depends(require_active_tenant), current_user: User = Depends(require_manager_or_above), db: Session = Depends(get_db)):
    """Create an administrative temporary hold for a slot.

    This endpoint is intentionally administrative in the MVP. When a hold is
    created from the customer portal in the future, use get_current_customer in
    that route and set customer_account_id from the authenticated customer.
    """
    if payload.expires_at <= datetime.now(timezone.utc):
        raise ValidationError("expires_at deve estar no futuro.")
    if payload.end_datetime <= payload.start_datetime:
        raise ValidationError("end_datetime deve ser posterior a start_datetime.")

    hold = AppointmentHold(
        tenant_id=tenant.id,
        customer_account_id=payload.customer_account_id,
        professional_id=payload.professional_id,
        start_datetime=payload.start_datetime,
        end_datetime=payload.end_datetime,
        service_ids=[str(s) for s in payload.service_ids],
        expires_at=payload.expires_at,
        status="active",
    )
    db.add(hold)
    db.flush()
    audit_service.log(db, "appointment_hold_created", "appointment_hold", hold.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(hold)
    return hold


@router.get("/appointment-holds/{hold_id}", response_model=AppointmentHoldResponse)
def get_hold(hold_id: uuid.UUID, tenant: Tenant = Depends(require_active_tenant), current_user: User = Depends(require_manager_or_above), db: Session = Depends(get_db)):
    hold = db.query(AppointmentHold).filter(
        AppointmentHold.id == hold_id,
        AppointmentHold.tenant_id == tenant.id,
    ).first()
    if not hold:
        raise NotFoundError("APPOINTMENT_HOLD_NOT_FOUND", "Reserva temporária não encontrada.")
    return hold


@router.post("/appointment-holds/{hold_id}/cancel")
def cancel_hold(hold_id: uuid.UUID, tenant: Tenant = Depends(require_active_tenant), current_user: User = Depends(require_manager_or_above), db: Session = Depends(get_db)):
    hold = db.query(AppointmentHold).filter(
        AppointmentHold.id == hold_id,
        AppointmentHold.tenant_id == tenant.id,
    ).first()
    if not hold:
        raise NotFoundError("APPOINTMENT_HOLD_NOT_FOUND", "Reserva temporária não encontrada.")
    hold.status = "cancelled"
    db.commit()
    return {"message": "Reserva cancelada."}
