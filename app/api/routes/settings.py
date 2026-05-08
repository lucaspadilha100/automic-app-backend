from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid

from db.session import get_db
from app.core.dependencies import require_active_tenant, require_manager_or_above
from app.models.user import User
from app.models.tenant import Tenant, TenantSettings, TenantTheme, TenantBookingPolicy, TenantPaymentSettings
from app.models.notification import NotificationTemplate
from app.models.webhook import WebhookEndpoint, WebhookDelivery
from app.services.feature_flag_service import feature_flag_service
from app.services.effective_plan_service import (
    effective_plan_service, PLAN_FEATURE_MAP, LIMIT_KEYS,
)
from app.services.audit_service import audit_service
from app.schemas.tenant import TenantSettingsUpdate, TenantThemeUpdate, BookingPolicyUpdate
from app.schemas.schemas import NotificationTemplateCreate, WebhookCreate, WebhookResponse, TenantPaymentSettingsUpdate, TenantPaymentSettingsResponse
from typing import List

router = APIRouter(prefix="/settings", tags=["Configurações do Tenant"])


# ---- Payment Settings / Manual Pix ----

@router.get("/payment", response_model=TenantPaymentSettingsResponse)
def get_payment_settings(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    payment_settings = db.query(TenantPaymentSettings).filter(TenantPaymentSettings.tenant_id == tenant.id).first()
    if not payment_settings:
        payment_settings = TenantPaymentSettings(tenant_id=tenant.id)
        db.add(payment_settings)
        db.commit()
        db.refresh(payment_settings)
    return payment_settings


@router.put("/payment", response_model=TenantPaymentSettingsResponse)
def update_payment_settings(
    payload: TenantPaymentSettingsUpdate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    payment_settings = db.query(TenantPaymentSettings).filter(TenantPaymentSettings.tenant_id == tenant.id).first()
    old_values = None
    if not payment_settings:
        payment_settings = TenantPaymentSettings(tenant_id=tenant.id)
        db.add(payment_settings)
    else:
        old_values = {
            "require_deposit_by_default": payment_settings.require_deposit_by_default,
            "default_deposit_type": payment_settings.default_deposit_type,
            "default_deposit_value": str(payment_settings.default_deposit_value),
            "require_deposit_for_first_appointment": payment_settings.require_deposit_for_first_appointment,
            "require_deposit_after_no_show": payment_settings.require_deposit_after_no_show,
            "pix_key": payment_settings.pix_key,
        }
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(payment_settings, k, v)
    db.flush()
    audit_service.log(db, "tenant_payment_settings_updated", "tenant_payment_settings", payment_settings.id, tenant.id, current_user.id, old_values=old_values)
    db.commit()
    db.refresh(payment_settings)
    return payment_settings


# ---- Public settings ----

@router.get("")
def get_settings(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    settings = db.query(TenantSettings).filter(TenantSettings.tenant_id == tenant.id).first()
    theme = db.query(TenantTheme).filter(TenantTheme.tenant_id == tenant.id).first()
    policy = db.query(TenantBookingPolicy).filter(TenantBookingPolicy.tenant_id == tenant.id).first()
    return {
        "settings": settings,
        "theme": theme,
        "booking_policy": policy,
    }


@router.get("/effective-features")
def get_effective_features(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    """Return the effective feature map and limits for the *current* tenant.

    Used by the frontend to hide menu entries for features that are off
    in the tenant's plan or that have been manually disabled by the master
    console. Internal-only — no customer access. Read-only.
    """
    features = {}
    for feature_key in PLAN_FEATURE_MAP:
        res = effective_plan_service.get_feature_source(db, tenant.id, feature_key)
        features[feature_key] = res or {"enabled": False, "source": "plan"}

    limits = {}
    for limit_key in LIMIT_KEYS:
        res = effective_plan_service.get_limit_source(db, tenant.id, limit_key)
        limits[limit_key] = res or {"value": None, "source": "plan"}

    return {
        "tenant_id": str(tenant.id),
        "features": features,
        "limits": limits,
    }


@router.get("/branding")
def get_tenant_branding(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    """Effective branding for the tenant's *internal* admin panel.

    Returns logo, name, colors and contact info from the tenant's own theme +
    main record. Used by the frontend to render the tenant's identity in
    the sidebar header, page title, favicon, emails preview, etc.

    This is **read-only** here. To edit branding, use:
      - PUT /settings/theme  (logo + colors + fonts)
      - PUT /settings/general (name, contact info, etc)
    """
    theme = db.query(TenantTheme).filter(TenantTheme.tenant_id == tenant.id).first()

    return {
        "tenant_id": str(tenant.id),
        "tenant_slug": tenant.slug,
        "company_name": tenant.public_name or tenant.name,
        "display_name": tenant.name,
        "logo_url": theme.logo_url if theme else None,
        "logo_small_url": theme.logo_small_url if theme else None,
        "favicon_url": theme.favicon_url if theme else None,
        "cover_image_url": theme.cover_image_url if theme else None,
        "primary_color": theme.primary_color if theme else None,
        "secondary_color": theme.secondary_color if theme else None,
        "background_color": theme.background_color if theme else None,
        "button_color": theme.button_color if theme else None,
        "text_color": theme.text_color if theme else None,
        "font_family": theme.font_family if theme else None,
        "visual_style": theme.visual_style if theme else None,
        "theme_preset": theme.theme_preset if theme else None,
        "support_email": tenant.email,
        "support_phone": tenant.phone,
        "whatsapp": tenant.whatsapp,
        "instagram": tenant.instagram,
        "website": tenant.website,
        "short_description": tenant.short_description,
    }


@router.put("/general")
def update_general_settings(
    payload: TenantSettingsUpdate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    settings = db.query(TenantSettings).filter(TenantSettings.tenant_id == tenant.id).first()
    if not settings:
        settings = TenantSettings(tenant_id=tenant.id)
        db.add(settings)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(settings, k, v)
    audit_service.log(db, "settings_updated", "tenant", tenant.id, tenant.id, current_user.id)
    db.commit()
    return {"message": "Configurações atualizadas."}


@router.put("/theme")
def update_theme(
    payload: TenantThemeUpdate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    theme = db.query(TenantTheme).filter(TenantTheme.tenant_id == tenant.id).first()
    if not theme:
        theme = TenantTheme(tenant_id=tenant.id)
        db.add(theme)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(theme, k, v)
    audit_service.log(db, "theme_updated", "tenant", tenant.id, tenant.id, current_user.id)
    db.commit()
    return {"message": "Tema atualizado."}


@router.put("/booking-policy")
def update_booking_policy(
    payload: BookingPolicyUpdate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    policy = db.query(TenantBookingPolicy).filter(TenantBookingPolicy.tenant_id == tenant.id).first()
    if not policy:
        policy = TenantBookingPolicy(tenant_id=tenant.id)
        db.add(policy)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(policy, k, v)
    audit_service.log(db, "booking_policy_updated", "tenant", tenant.id, tenant.id, current_user.id)
    db.commit()
    return {"message": "Política de agendamento atualizada."}


# ---- Notification Templates ----

@router.get("/notifications", tags=["Notificações"])
def list_notification_templates(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return db.query(NotificationTemplate).filter(NotificationTemplate.tenant_id == tenant.id).all()


@router.post("/notifications", tags=["Notificações"])
def create_notification_template(
    payload: NotificationTemplateCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    tmpl = NotificationTemplate(tenant_id=tenant.id, **payload.model_dump())
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl


@router.put("/notifications/{template_id}", tags=["Notificações"])
def update_notification_template(
    template_id: uuid.UUID,
    payload: NotificationTemplateCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    from app.core.exceptions import NotFoundError
    tmpl = db.query(NotificationTemplate).filter(
        NotificationTemplate.id == template_id, NotificationTemplate.tenant_id == tenant.id
    ).first()
    if not tmpl:
        raise NotFoundError("TEMPLATE_NOT_FOUND", "Template não encontrado.")
    for k, v in payload.model_dump().items():
        setattr(tmpl, k, v)
    db.commit()
    return tmpl


# ---- Webhooks ----

@router.get("/webhooks", response_model=List[WebhookResponse], tags=["Webhooks"])
def list_webhooks(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    feature_flag_service.require_feature(db, tenant, "webhooks")
    return db.query(WebhookEndpoint).filter(WebhookEndpoint.tenant_id == tenant.id).all()


@router.post("/webhooks", response_model=WebhookResponse, tags=["Webhooks"])
def create_webhook(
    payload: WebhookCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    feature_flag_service.require_feature(db, tenant, "webhooks")
    ep = WebhookEndpoint(
        tenant_id=tenant.id,
        url=payload.url,
        secret=payload.secret,
        event_types=payload.event_types,
        is_active=payload.is_active,
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


@router.put("/webhooks/{webhook_id}", response_model=WebhookResponse, tags=["Webhooks"])
def update_webhook(
    webhook_id: uuid.UUID,
    payload: WebhookCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    from app.core.exceptions import NotFoundError
    feature_flag_service.require_feature(db, tenant, "webhooks")
    ep = db.query(WebhookEndpoint).filter(
        WebhookEndpoint.id == webhook_id, WebhookEndpoint.tenant_id == tenant.id
    ).first()
    if not ep:
        raise NotFoundError("WEBHOOK_NOT_FOUND", "Webhook não encontrado.")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(ep, k, v)
    db.commit()
    db.refresh(ep)
    return ep


@router.delete("/webhooks/{webhook_id}", tags=["Webhooks"])
def delete_webhook(
    webhook_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    from app.core.exceptions import NotFoundError
    feature_flag_service.require_feature(db, tenant, "webhooks")
    ep = db.query(WebhookEndpoint).filter(
        WebhookEndpoint.id == webhook_id, WebhookEndpoint.tenant_id == tenant.id
    ).first()
    if not ep:
        raise NotFoundError("WEBHOOK_NOT_FOUND", "Webhook não encontrado.")
    db.delete(ep)
    db.commit()
    return {"message": "Webhook removido."}
