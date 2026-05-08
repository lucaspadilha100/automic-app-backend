from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import require_active_tenant, require_manager_or_above
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.whatsapp import (
    TenantWhatsAppSettingsResponse, TenantWhatsAppSettingsUpdate,
    TenantWhatsAppStatusResponse, TenantWhatsAppStatusUpdate,
)
from app.services.whatsapp_settings_service import whatsapp_settings_service

router = APIRouter(prefix="/admin/integrations/whatsapp", tags=["WhatsApp / n8n Integration"])


@router.get("", response_model=TenantWhatsAppSettingsResponse)
def get_whatsapp_settings(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return whatsapp_settings_service.get_settings(db=db, tenant=tenant)


@router.put("", response_model=TenantWhatsAppSettingsResponse)
def upsert_whatsapp_settings(
    payload: TenantWhatsAppSettingsUpdate,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return whatsapp_settings_service.upsert_settings(
        db=db, tenant=tenant,
        data=payload.model_dump(exclude_none=True),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.get("/status", response_model=TenantWhatsAppStatusResponse)
def get_whatsapp_status(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    s = whatsapp_settings_service.get_status(db=db, tenant=tenant)
    return TenantWhatsAppStatusResponse(
        tenant_id=s.tenant_id,
        enabled=s.enabled,
        status=s.status,
        provider=s.provider,
        last_connected_at=s.last_connected_at,
    )


@router.patch("/status", response_model=TenantWhatsAppStatusResponse)
def update_whatsapp_status(
    payload: TenantWhatsAppStatusUpdate,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    s = whatsapp_settings_service.update_status(
        db=db, tenant=tenant, status=payload.status,
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return TenantWhatsAppStatusResponse(
        tenant_id=s.tenant_id,
        enabled=s.enabled,
        status=s.status,
        provider=s.provider,
        last_connected_at=s.last_connected_at,
    )
