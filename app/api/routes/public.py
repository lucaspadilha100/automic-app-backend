from typing import List, Optional
from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session
import uuid

from db.session import get_db
from app.core.dependencies import get_public_tenant_by_slug, get_optional_customer
from app.core.exceptions import CustomerNotFoundError, ForbiddenError, InvalidBookingPolicyError
from app.models.tenant import Tenant, TenantSettings, TenantTheme, TenantBookingPolicy
from app.models.customer import CustomerAccount, TenantCustomer
from app.models.appointment import Appointment
from app.models.service import Service, ServiceCategory
from app.models.professional import Professional
from app.models.schedule import BusinessHour
from app.models.procedure_photo import ProcedurePhoto, PhotoVisibility
from app.models.media import MediaFile
from app.services.appointment_service import appointment_service
from app.services.audit_service import audit_service
from app.schemas.schemas import AppointmentCreate, AppointmentResponse, AppointmentCancelRequest

router = APIRouter(prefix="/public", tags=["Página Pública de Agendamento"])


@router.get("/{slug}")
def get_public_info(slug: str, db: Session = Depends(get_db)):
    """Retorna informações públicas do tenant para a página de agendamento."""
    tenant = get_public_tenant_by_slug(slug, db)

    settings = db.query(TenantSettings).filter(TenantSettings.tenant_id == tenant.id).first()
    theme = db.query(TenantTheme).filter(TenantTheme.tenant_id == tenant.id).first()
    policy = db.query(TenantBookingPolicy).filter(TenantBookingPolicy.tenant_id == tenant.id).first()
    hours = db.query(BusinessHour).filter(BusinessHour.tenant_id == tenant.id).order_by(BusinessHour.weekday).all()

    return {
        "tenant": {
            "name": tenant.public_name or tenant.name,
            "short_description": tenant.short_description,
            "category": tenant.category,
            "phone": tenant.phone if (settings and settings.show_whatsapp) else None,
            "whatsapp": tenant.whatsapp if (settings and settings.show_whatsapp) else None,
            "address": tenant.address if (settings and settings.show_address) else None,
            "instagram": tenant.instagram if (settings and settings.show_instagram) else None,
        },
        "theme": {
            "logo_url": theme.logo_url if theme else None,
            "cover_image_url": theme.cover_image_url if theme else None,
            "primary_color": theme.primary_color if theme else None,
            "secondary_color": theme.secondary_color if theme else None,
            "background_color": theme.background_color if theme else None,
            "button_color": theme.button_color if theme else None,
            "font_family": theme.font_family if theme else None,
            "theme_preset": theme.theme_preset if theme else "classic",
        } if theme else {},
        "settings": {
            "show_prices": settings.show_prices if settings else True,
            "show_duration": settings.show_duration if settings else True,
            "allow_professional_choice": settings.allow_professional_choice if settings else True,
            "allow_any_professional": settings.allow_any_professional if settings else True,
            "allow_multiple_services": settings.allow_multiple_services if settings else True,
            "allow_customer_cancel": settings.allow_customer_cancel if settings else True,
            "allow_customer_reschedule": settings.allow_customer_reschedule if settings else True,
            "require_customer_cpf": settings.require_customer_cpf if settings else False,
            "require_terms_acceptance": settings.require_terms_acceptance if settings else False,
            "homepage_title": settings.homepage_title if settings else None,
            "homepage_subtitle": settings.homepage_subtitle if settings else None,
            "confirmation_message": settings.confirmation_message if settings else None,
            "terms_text": settings.terms_text if settings else None,
            "cancellation_policy_text": settings.cancellation_policy_text if settings else None,
        } if settings else {},
        "booking_policy": {
            "min_minutes_before_booking": policy.min_minutes_before_booking if policy else 60,
            "max_days_ahead_booking": policy.max_days_ahead_booking if policy else 60,
            "slot_interval_minutes": policy.slot_interval_minutes if policy else 30,
        } if policy else {},
        "business_hours": [
            {
                "weekday": bh.weekday,
                "open_time": bh.open_time.strftime("%H:%M") if bh.open_time else None,
                "close_time": bh.close_time.strftime("%H:%M") if bh.close_time else None,
                "is_closed": bh.is_closed,
            }
            for bh in hours
        ],
    }


@router.get("/{slug}/services")
def get_public_services(slug: str, db: Session = Depends(get_db)):
    tenant = get_public_tenant_by_slug(slug, db)
    settings = db.query(TenantSettings).filter(TenantSettings.tenant_id == tenant.id).first()

    categories = db.query(ServiceCategory).filter(
        ServiceCategory.tenant_id == tenant.id, ServiceCategory.is_active == True
    ).order_by(ServiceCategory.sort_order).all()

    services = db.query(Service).filter(
        Service.tenant_id == tenant.id, Service.is_active == True, Service.deleted_at.is_(None)
    ).all()

    show_prices = settings.show_prices if settings else True
    show_duration = settings.show_duration if settings else True

    return {
        "categories": [{"id": str(c.id), "name": c.name, "description": c.description} for c in categories],
        "services": [
            {
                "id": str(s.id),
                "name": s.name,
                "description": s.description,
                "category_id": str(s.category_id) if s.category_id else None,
                "price": float(s.price) if show_prices else None,
                "duration_minutes": s.duration_minutes if show_duration else None,
                "requires_deposit": s.requires_deposit,
                "image_url": s.image_url,
            }
            for s in services
        ],
    }


@router.get("/{slug}/professionals")
def get_public_professionals(slug: str, db: Session = Depends(get_db)):
    tenant = get_public_tenant_by_slug(slug, db)
    settings = db.query(TenantSettings).filter(TenantSettings.tenant_id == tenant.id).first()
    if settings and not settings.show_professionals:
        return []

    professionals = db.query(Professional).filter(
        Professional.tenant_id == tenant.id,
        Professional.is_active == True,
        Professional.deleted_at.is_(None),
    ).all()

    return [
        {
            "id": str(p.id),
            "name": p.name,
            "bio": p.bio,
            "photo_url": p.photo_url,
            "service_ids": [str(ps.service_id) for ps in p.professional_services],
        }
        for p in professionals
    ]


@router.post("/{slug}/appointments", response_model=AppointmentResponse)
def book_public(
    slug: str,
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    current_customer: Optional[CustomerAccount] = Depends(get_optional_customer),
):
    """Agendamento pelo cliente na página pública."""
    tenant = get_public_tenant_by_slug(slug, db)

    # Customer must be authenticated or account_id must match token
    if not current_customer:
        raise ForbiddenError("Faça login para agendar.")

    if payload.customer_account_id and str(payload.customer_account_id) != str(current_customer.id):
        raise ForbiddenError("Identificação de cliente inválida.")

    # Ensure tenant_customer link exists
    tc = db.query(TenantCustomer).filter(
        TenantCustomer.tenant_id == tenant.id,
        TenantCustomer.customer_account_id == current_customer.id,
    ).first()

    if not tc:
        tc = TenantCustomer(
            tenant_id=tenant.id,
            customer_account_id=current_customer.id,
        )
        db.add(tc)
        db.flush()

    appt = appointment_service.create(
        db=db,
        tenant=tenant,
        professional_id=payload.professional_id,
        service_ids=payload.service_ids,
        start_datetime=payload.start_datetime,
        customer_account_id=current_customer.id,
        tenant_customer_id=tc.id,
        customer_notes=payload.customer_notes,
        source="public_page",
        idempotency_key=payload.idempotency_key,
        customer_package_id=payload.customer_package_id,
    )
    db.commit()
    db.refresh(appt)
    return appt


@router.post("/{slug}/appointments/{appointment_id}/cancel")
def cancel_public(
    slug: str,
    appointment_id: uuid.UUID,
    payload: AppointmentCancelRequest,
    db: Session = Depends(get_db),
    current_customer: CustomerAccount = Depends(get_optional_customer),
):
    tenant = get_public_tenant_by_slug(slug, db)
    if not current_customer:
        raise ForbiddenError("Faça login para cancelar.")

    appt = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.tenant_id == tenant.id,
        Appointment.customer_account_id == current_customer.id,
    ).first()
    if not appt:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("APPOINTMENT_NOT_FOUND", "Agendamento não encontrado.")

    # Check cancellation policy
    from app.models.tenant import TenantBookingPolicy
    from datetime import datetime, timezone, timedelta
    policy = db.query(TenantBookingPolicy).filter(TenantBookingPolicy.tenant_id == tenant.id).first()
    if policy and not policy.allow_customer_cancel:
        raise InvalidBookingPolicyError("Cancelamento pelo cliente não está habilitado.")

    if policy and policy.min_hours_before_cancel:
        min_cancel_dt = datetime.now(timezone.utc) + timedelta(hours=policy.min_hours_before_cancel)
        if appt.start_datetime < min_cancel_dt:
            raise InvalidBookingPolicyError(
                f"O cancelamento deve ser feito com pelo menos {policy.min_hours_before_cancel}h de antecedência."
            )

    appointment_service.cancel(db, appt, "customer", current_customer.id, payload.reason)
    db.commit()
    return {"message": "Agendamento cancelado."}


@router.get("/{slug}/photos")
def get_public_photos(slug: str, limit: int = Query(20, le=50), db: Session = Depends(get_db)):
    """Fotos públicas do portfólio do tenant."""
    tenant = get_public_tenant_by_slug(slug, db)

    photos = (
        db.query(ProcedurePhoto)
        .join(MediaFile, ProcedurePhoto.media_file_id == MediaFile.id)
        .filter(
            ProcedurePhoto.tenant_id == tenant.id,
            ProcedurePhoto.visibility == PhotoVisibility.public,
        )
        .order_by(ProcedurePhoto.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": str(p.id),
            "photo_type": p.photo_type.value if p.photo_type else "other",
            "caption": p.caption,
            "file_url": p.media_file.file_url if p.media_file else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in photos
    ]


@router.get("/{slug}/reviews")
def get_public_reviews(slug: str, limit: int = Query(20, le=50), db: Session = Depends(get_db)):
    """Avaliações públicas do tenant."""
    tenant = get_public_tenant_by_slug(slug, db)

    try:
        from app.models.future import AppointmentReview
        reviews = (
            db.query(AppointmentReview)
            .filter(
                AppointmentReview.tenant_id == tenant.id,
                AppointmentReview.visibility == "public",
            )
            .order_by(AppointmentReview.created_at.desc())
            .limit(limit)
            .all()
        )

        result = []
        for r in reviews:
            reviewer_name = None
            if r.customer_account:
                name = r.customer_account.name or ""
                parts = name.split()
                reviewer_name = f"{parts[0]} {parts[1][0]}." if len(parts) > 1 else parts[0] if parts else "Cliente"

            result.append({
                "id": str(r.id),
                "rating": r.rating,
                "comment": r.comment,
                "reviewer_name": reviewer_name,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })

        return result
    except Exception:
        return []


@router.get("/{slug}/my-appointments")
def my_appointments(
    slug: str,
    db: Session = Depends(get_db),
    current_customer: CustomerAccount = Depends(get_optional_customer),
):
    tenant = get_public_tenant_by_slug(slug, db)
    if not current_customer:
        raise ForbiddenError("Faça login.")

    appts = db.query(Appointment).filter(
        Appointment.tenant_id == tenant.id,
        Appointment.customer_account_id == current_customer.id,
    ).order_by(Appointment.start_datetime.desc()).limit(50).all()
    return appts
