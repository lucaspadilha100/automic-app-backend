from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime
import uuid


_HEX_COLOR_RE = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"


def _validate_hex_color(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    import re
    if not re.match(_HEX_COLOR_RE, v):
        raise ValueError(f"Cor inválida: {v}. Use #RRGGBB ou #RGB.")
    return v


class PlatformSettingsResponse(BaseModel):
    id: uuid.UUID
    platform_name: str
    platform_tagline: Optional[str]
    platform_legal_name: Optional[str]
    platform_cnpj: Optional[str]
    logo_url: Optional[str]
    logo_dark_url: Optional[str]
    favicon_url: Optional[str]
    primary_color: str
    secondary_color: str
    accent_color: Optional[str]
    support_email: Optional[str]
    support_phone: Optional[str]
    support_url: Optional[str]
    sales_email: Optional[str]
    sales_phone: Optional[str]
    primary_domain: Optional[str]
    marketing_url: Optional[str]
    instagram_url: Optional[str]
    linkedin_url: Optional[str]
    terms_of_service_url: Optional[str]
    privacy_policy_url: Optional[str]
    owner_notification_emails: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlatformSettingsUpdate(BaseModel):
    """All fields optional — partial update of the singleton row."""
    platform_name: Optional[str] = None
    platform_tagline: Optional[str] = None
    platform_legal_name: Optional[str] = None
    platform_cnpj: Optional[str] = None
    logo_url: Optional[str] = None
    logo_dark_url: Optional[str] = None
    favicon_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    support_email: Optional[str] = None
    support_phone: Optional[str] = None
    support_url: Optional[str] = None
    sales_email: Optional[str] = None
    sales_phone: Optional[str] = None
    primary_domain: Optional[str] = None
    marketing_url: Optional[str] = None
    instagram_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    terms_of_service_url: Optional[str] = None
    privacy_policy_url: Optional[str] = None
    owner_notification_emails: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("primary_color", "secondary_color", "accent_color")
    @classmethod
    def validate_colors(cls, v: Optional[str]) -> Optional[str]:
        return _validate_hex_color(v)

    @field_validator("platform_name")
    @classmethod
    def validate_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("platform_name não pode estar vazio.")
        return v


class PublicPlatformBranding(BaseModel):
    """Subset of platform settings exposed publicly (no auth) — useful for
    the login/register pages of the master console to render the AUTOMIC
    brand even before the user logs in."""
    platform_name: str
    platform_tagline: Optional[str]
    logo_url: Optional[str]
    logo_dark_url: Optional[str]
    favicon_url: Optional[str]
    primary_color: str
    secondary_color: str
    accent_color: Optional[str]
    support_email: Optional[str]
    support_url: Optional[str]
    marketing_url: Optional[str]
    terms_of_service_url: Optional[str]
    privacy_policy_url: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class TenantBrandingResponse(BaseModel):
    """Effective branding to be applied to the tenant's *internal* admin panel.

    This is consumed by the frontend in `AppLayout`/header/title/favicon to
    render the tenant's own logo, name and colors instead of AUTOMIC's.
    """
    tenant_id: uuid.UUID
    tenant_slug: str
    company_name: Optional[str]    # from Tenant.public_name when set, else Tenant.name
    display_name: str              # tenant.name (always present)
    logo_url: Optional[str]
    logo_small_url: Optional[str]
    favicon_url: Optional[str]
    cover_image_url: Optional[str]
    primary_color: Optional[str]
    secondary_color: Optional[str]
    background_color: Optional[str]
    button_color: Optional[str]
    text_color: Optional[str]
    font_family: Optional[str]
    visual_style: Optional[str]
    theme_preset: Optional[str]
    support_email: Optional[str]
    support_phone: Optional[str]
    whatsapp: Optional[str]
    instagram: Optional[str]
    website: Optional[str]
    short_description: Optional[str]

    model_config = ConfigDict(from_attributes=True)
