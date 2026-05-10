from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from datetime import datetime
import uuid


class TenantCreate(BaseModel):
    name: str
    slug: str
    timezone: str = "America/Sao_Paulo"
    status: str = "trial"
    email: Optional[str] = None
    phone: Optional[str] = None


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    timezone: Optional[str] = None
    public_name: Optional[str] = None
    short_description: Optional[str] = None
    category: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    instagram: Optional[str] = None
    website: Optional[str] = None


class TenantStatusUpdate(BaseModel):
    status: str  # active | inactive | suspended | cancelled | trial


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str
    timezone: str
    email: Optional[str] = None
    phone: Optional[str] = None
    public_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlanCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price_monthly: float = 0
    max_services: Optional[int] = None
    max_professionals: Optional[int] = None
    max_users: Optional[int] = None
    max_appointments_per_month: Optional[int] = None
    max_units: int = 1
    max_packages: Optional[int] = None
    allow_online_payment: bool = False
    allow_packages: bool = True
    allow_custom_terms: bool = False
    allow_advanced_reports: bool = False
    allow_crm_integration: bool = False
    allow_before_after_photos: bool = False
    allow_multi_unit: bool = False
    allow_waitlist: bool = False
    allow_physical_resources: bool = False
    allow_webhooks: bool = False
    allow_custom_forms: bool = False
    allow_customer_lifecycle: bool = False
    allow_automation_rules: bool = False
    allow_whatsapp_integration: bool = False
    allow_commissions: bool = False


class PlanResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    price_monthly: float
    max_services: Optional[int] = None
    max_professionals: Optional[int] = None
    max_users: Optional[int] = None
    max_appointments_per_month: Optional[int] = None
    max_units: int
    max_packages: Optional[int] = None
    allow_online_payment: bool
    allow_packages: bool
    allow_custom_terms: bool = False
    allow_advanced_reports: bool = False
    allow_crm_integration: bool = False
    allow_before_after_photos: bool = False
    allow_multi_unit: bool = False
    allow_waitlist: bool = False
    allow_physical_resources: bool = False
    allow_webhooks: bool = False
    allow_custom_forms: bool = False
    allow_customer_lifecycle: bool = False
    allow_automation_rules: bool = False
    allow_whatsapp_integration: bool = False
    allow_commissions: bool = False
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class SubscriptionUpdate(BaseModel):
    plan_id: uuid.UUID
    status: Optional[str] = None
    trial_ends_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    # Commercial overrides — all optional; pass them only when negotiating.
    custom_price_monthly: Optional[float] = None
    custom_price_reason: Optional[str] = None
    billing_notes: Optional[str] = None
    contracted_at: Optional[datetime] = None

    @field_validator("custom_price_monthly")
    @classmethod
    def _custom_price_non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("custom_price_monthly não pode ser negativo")
        return v


class LimitOverrideUpdate(BaseModel):
    max_services: Optional[int] = None
    max_professionals: Optional[int] = None
    max_users: Optional[int] = None
    max_appointments_per_month: Optional[int] = None
    max_units: Optional[int] = None
    max_packages: Optional[int] = None
    notes: Optional[str] = None


class FeatureFlagUpdate(BaseModel):
    feature_key: str
    enabled: bool
    source: str = "manual"


class TenantSettingsUpdate(BaseModel):
    show_prices: Optional[bool] = None
    show_duration: Optional[bool] = None
    show_professionals: Optional[bool] = None
    allow_professional_choice: Optional[bool] = None
    allow_any_professional: Optional[bool] = None
    allow_multiple_services: Optional[bool] = None
    allow_customer_cancel: Optional[bool] = None
    allow_customer_reschedule: Optional[bool] = None
    require_customer_cpf: Optional[bool] = None
    require_customer_birth_date: Optional[bool] = None
    require_terms_acceptance: Optional[bool] = None
    require_deposit_payment: Optional[bool] = None
    allow_online_payment: Optional[bool] = None
    homepage_title: Optional[str] = None
    homepage_subtitle: Optional[str] = None
    primary_button_text: Optional[str] = None
    confirmation_message: Optional[str] = None
    cancellation_message: Optional[str] = None
    footer_text: Optional[str] = None
    terms_text: Optional[str] = None
    privacy_text: Optional[str] = None
    no_show_policy_text: Optional[str] = None
    no_show_limit_before_deposit_required: Optional[int] = None
    auto_require_deposit_after_no_show: Optional[bool] = None
    consume_package_session_on_no_show: Optional[bool] = None
    cancellation_policy_text: Optional[str] = None


class TenantThemeUpdate(BaseModel):
    logo_url: Optional[str] = None
    logo_small_url: Optional[str] = None
    favicon_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    background_color: Optional[str] = None
    button_color: Optional[str] = None
    text_color: Optional[str] = None
    font_family: Optional[str] = None
    visual_style: Optional[str] = None
    theme_preset: Optional[str] = None


class PageSectionItem(BaseModel):
    visible: Optional[bool] = None
    label: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    background_color: Optional[str] = None
    background_image_url: Optional[str] = None
    overlay_opacity: Optional[float] = None
    cta_text: Optional[str] = None


class PageSectionsUpdate(BaseModel):
    hero: Optional[PageSectionItem] = None
    about: Optional[PageSectionItem] = None
    services: Optional[PageSectionItem] = None
    team: Optional[PageSectionItem] = None
    products: Optional[PageSectionItem] = None
    portfolio: Optional[PageSectionItem] = None
    reviews: Optional[PageSectionItem] = None
    footer: Optional[PageSectionItem] = None


class BookingPolicyUpdate(BaseModel):
    min_minutes_before_booking: Optional[int] = None
    max_days_ahead_booking: Optional[int] = None
    slot_interval_minutes: Optional[int] = None
    min_hours_before_cancel: Optional[int] = None
    min_hours_before_reschedule: Optional[int] = None
    allow_customer_cancel: Optional[bool] = None
    allow_customer_reschedule: Optional[bool] = None
    require_cancel_reason: Optional[bool] = None
    cancellation_policy_text: Optional[str] = None
    no_show_policy_text: Optional[str] = None
    no_show_limit_before_deposit_required: Optional[int] = None
    auto_require_deposit_after_no_show: Optional[bool] = None
    consume_package_session_on_no_show: Optional[bool] = None
# BookingPolicyUpdate audit-gap fields (kept at class level by monkey patch via subclass is not needed for Pydantic;
# these names are repeated here for documentation only if the old class is imported elsewhere.)
