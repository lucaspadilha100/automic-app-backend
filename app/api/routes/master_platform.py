"""
Routes for the AUTOMIC platform itself (super_admin only).

These configure the SaaS owner's identity and branding — the AUTOMIC logo,
support contacts, legal URLs, owner notification settings, etc.

Distinct from tenant-level branding (`/admin/branding`, /master/tenants/.../theme).
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import require_super_admin
from app.models.user import User
from app.models.platform_document import PlatformDocumentType
from app.schemas.platform_settings import (
    PlatformSettingsResponse,
    PlatformSettingsUpdate,
    PublicPlatformBranding,
)
from app.schemas.platform_document import (
    PlatformDocumentResponse,
    PlatformDocumentUpsert,
)
from app.services.platform_settings_service import platform_settings_service
from app.services.platform_document_service import platform_document_service

router = APIRouter(prefix="/master/platform", tags=["Plataforma AUTOMIC"])


@router.get("/settings", response_model=PlatformSettingsResponse)
def get_platform_settings(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return platform_settings_service.get_or_create(db)


@router.put("/settings", response_model=PlatformSettingsResponse)
def update_platform_settings(
    payload: PlatformSettingsUpdate,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return platform_settings_service.update(
        db=db,
        data=payload.model_dump(exclude_unset=True),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


# ── Public endpoint (no auth) ─────────────────────────────────────────────────
# Used by the master console login/forgot-password pages so they show the
# AUTOMIC brand correctly even before login. Returns a *subset* of the
# settings — never owner_notification_emails, cnpj, notes, etc.

public_router = APIRouter(prefix="/public/platform", tags=["Plataforma AUTOMIC - Público"])


@public_router.get("/branding", response_model=PublicPlatformBranding)
def get_public_platform_branding(db: Session = Depends(get_db)):
    return platform_settings_service.get_or_create(db)


# ── Documents (legal copy of the AUTOMIC platform) ────────────────────────────
@router.get("/documents/{document_type}", response_model=PlatformDocumentResponse)
def get_platform_document(
    document_type: PlatformDocumentType,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return platform_document_service.get_or_404(db, document_type)


@router.put("/documents/{document_type}", response_model=PlatformDocumentResponse)
def upsert_platform_document(
    document_type: PlatformDocumentType,
    payload: PlatformDocumentUpsert,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return platform_document_service.upsert(
        db, document_type,
        title=payload.title, content=payload.content, version=payload.version,
    )


@public_router.get("/documents/{document_type}", response_model=PlatformDocumentResponse)
def get_public_platform_document(
    document_type: PlatformDocumentType,
    db: Session = Depends(get_db),
):
    """Public read of a legal document (ToS / privacy) by type."""
    return platform_document_service.get_or_404(db, document_type)
