import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, Integer, Text, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint, Numeric, JSON
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class Tenant(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "tenants"

    # Identity
    name = Column(String(200), nullable=False)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default="trial")
    # status: trial | active | suspended | cancelled | inactive

    # Contact
    public_name = Column(String(200))
    short_description = Column(Text)
    category = Column(String(100))
    phone = Column(String(30))
    whatsapp = Column(String(30))
    email = Column(String(200))
    address = Column(Text)
    instagram = Column(String(200))
    website = Column(String(300))

    # Domain
    custom_domain = Column(String(300), nullable=True)
    custom_domain_enabled = Column(Boolean, default=False)

    # Timezone
    timezone = Column(String(60), default="America/Sao_Paulo", nullable=False)

    # Soft delete
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    subscriptions = relationship("TenantSubscription", back_populates="tenant", cascade="all, delete-orphan")
    limit_override = relationship("TenantLimitOverride", back_populates="tenant", uselist=False, cascade="all, delete-orphan")
    feature_flags = relationship("TenantFeatureFlag", back_populates="tenant", cascade="all, delete-orphan")
    settings = relationship("TenantSettings", back_populates="tenant", uselist=False, cascade="all, delete-orphan")
    theme = relationship("TenantTheme", back_populates="tenant", uselist=False, cascade="all, delete-orphan")
    booking_policy = relationship("TenantBookingPolicy", back_populates="tenant", uselist=False, cascade="all, delete-orphan")
    payment_settings = relationship("TenantPaymentSettings", back_populates="tenant", uselist=False, cascade="all, delete-orphan")
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    service_categories = relationship("ServiceCategory", back_populates="tenant", cascade="all, delete-orphan")
    services = relationship("Service", back_populates="tenant", cascade="all, delete-orphan")
    professionals = relationship("Professional", back_populates="tenant", cascade="all, delete-orphan")
    business_hours = relationship("BusinessHour", back_populates="tenant", cascade="all, delete-orphan")
    blocked_times = relationship("BlockedTime", back_populates="tenant", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="tenant", cascade="all, delete-orphan")
    units = relationship("Unit", back_populates="tenant", cascade="all, delete-orphan")
    packages = relationship("Package", back_populates="tenant", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="tenant")
    terms = relationship("TenantTerm", back_populates="tenant", cascade="all, delete-orphan")
    webhook_endpoints = relationship("WebhookEndpoint", back_populates="tenant", cascade="all, delete-orphan")
    product_categories = relationship("ProductCategory", back_populates="tenant", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="tenant", cascade="all, delete-orphan")
    product_orders = relationship("ProductOrder", back_populates="tenant", cascade="all, delete-orphan")
    supplies = relationship("Supply", back_populates="tenant", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('trial','active','suspended','cancelled','inactive')", name="ck_tenants_status"),
    )


class TenantSubscription(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "tenant_subscriptions"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False)
    status = Column(String(20), nullable=False, default="trial")
    starts_at = Column(DateTime(timezone=True), nullable=True)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)

    # Commercial overrides — negotiated price per tenant.
    # When custom_price_monthly is NULL, MRR uses the plan's price_monthly.
    custom_price_monthly = Column(Numeric(10, 2), nullable=True)
    custom_price_reason = Column(Text, nullable=True)
    billing_notes = Column(Text, nullable=True)
    contracted_at = Column(DateTime(timezone=True), nullable=True)

    # Onboarding — terms acceptance at signup time
    accepted_terms_at = Column(DateTime(timezone=True), nullable=True)
    accepted_terms_version = Column(String(20), nullable=True)
    signup_source = Column(String(50), nullable=True)  # e.g. 'self_service', 'manual_master'

    # Billing mode — controls how the cron treats this subscription:
    #   - manual    (default): cron generates invoices but never suspends/cancels.
    #                You handle payments and status changes manually.
    #   - automatic: cron generates invoices AND suspends/cancels by overdue rules.
    #                Use this once a real payment provider (Mercado Pago) is wired.
    #   - free:     no invoice generation, cron never touches. Useful for VIPs,
    #                internal accounts, beta testers, founder pricing.
    billing_mode = Column(String(20), nullable=False, default="manual")

    tenant = relationship("Tenant", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")

    __table_args__ = (
        CheckConstraint("status IN ('trial','active','suspended','cancelled','past_due')", name="ck_tenant_subscriptions_status"),
        CheckConstraint(
            "custom_price_monthly IS NULL OR custom_price_monthly >= 0",
            name="ck_tenant_subscriptions_custom_price_non_negative",
        ),
        CheckConstraint(
            "billing_mode IN ('manual','automatic','free')",
            name="ck_tenant_subscriptions_billing_mode",
        ),
    )


class TenantLimitOverride(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "tenant_limit_overrides"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)
    max_services = Column(Integer, nullable=True)
    max_professionals = Column(Integer, nullable=True)
    max_users = Column(Integer, nullable=True)
    max_appointments_per_month = Column(Integer, nullable=True)
    max_units = Column(Integer, nullable=True)
    max_packages = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)

    tenant = relationship("Tenant", back_populates="limit_override")


class TenantFeatureFlag(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "tenant_feature_flags"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    feature_key = Column(String(100), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    source = Column(String(20), default="plan")
    # source: plan | override | manual

    tenant = relationship("Tenant", back_populates="feature_flags")

    __table_args__ = (
        UniqueConstraint("tenant_id", "feature_key", name="uq_tenant_feature_flags_tenant_id_feature_key"),
    )


class TenantSettings(Base, UUIDPrimaryKey, TimestampMixin):
    """Public-facing and visual settings for the tenant."""
    __tablename__ = "tenant_settings"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Public settings
    show_prices = Column(Boolean, default=True)
    show_duration = Column(Boolean, default=True)
    show_professionals = Column(Boolean, default=True)
    allow_professional_choice = Column(Boolean, default=True)
    allow_any_professional = Column(Boolean, default=True)
    allow_multiple_services = Column(Boolean, default=True)
    allow_customer_cancel = Column(Boolean, default=True)
    allow_customer_reschedule = Column(Boolean, default=True)
    require_customer_cpf = Column(Boolean, default=False)
    require_customer_birth_date = Column(Boolean, default=False)
    require_terms_acceptance = Column(Boolean, default=False)
    require_deposit_payment = Column(Boolean, default=False)
    allow_online_payment = Column(Boolean, default=False)
    show_instagram = Column(Boolean, default=True)
    show_whatsapp = Column(Boolean, default=True)
    show_address = Column(Boolean, default=True)

    # Customizable texts
    homepage_title = Column(String(300))
    homepage_subtitle = Column(Text)
    primary_button_text = Column(String(100))
    confirmation_message = Column(Text)
    cancellation_message = Column(Text)
    payment_pending_message = Column(Text)
    footer_text = Column(Text)
    terms_text = Column(Text)
    privacy_text = Column(Text)
    no_show_policy_text = Column(Text)
    cancellation_policy_text = Column(Text)

    # Per-section page customization (JSONB)
    page_sections = Column(JSONB, nullable=True)

    tenant = relationship("Tenant", back_populates="settings")




class ThemePreset(Base, UUIDPrimaryKey, TimestampMixin):
    """Global white-label theme presets suggested for new tenants."""
    __tablename__ = "theme_presets"

    key = Column(String(80), nullable=False, unique=True, index=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    primary_color = Column(String(20), nullable=True)
    secondary_color = Column(String(20), nullable=True)
    background_color = Column(String(20), nullable=True)
    button_color = Column(String(20), nullable=True)
    text_color = Column(String(20), nullable=True)
    font_family = Column(String(100), nullable=True)
    visual_style = Column(String(50), nullable=True)
    default_texts = Column(JSONB, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

class TenantTheme(Base, UUIDPrimaryKey, TimestampMixin):
    """Visual identity for white label."""
    __tablename__ = "tenant_themes"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)

    logo_url = Column(String(500))
    logo_small_url = Column(String(500))
    favicon_url = Column(String(500))
    cover_image_url = Column(String(500))
    primary_color = Column(String(20))
    secondary_color = Column(String(20))
    background_color = Column(String(20))
    button_color = Column(String(20))
    text_color = Column(String(20))
    font_family = Column(String(100))
    visual_style = Column(String(50))
    theme_preset = Column(String(50))

    tenant = relationship("Tenant", back_populates="theme")


class TenantBookingPolicy(Base, UUIDPrimaryKey, TimestampMixin):
    """Booking, cancellation and rescheduling rules per tenant."""
    __tablename__ = "tenant_booking_policies"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)

    min_minutes_before_booking = Column(Integer, default=60)
    max_days_ahead_booking = Column(Integer, default=60)
    slot_interval_minutes = Column(Integer, default=30)
    min_hours_before_cancel = Column(Integer, default=24)
    min_hours_before_reschedule = Column(Integer, default=24)
    allow_customer_cancel = Column(Boolean, default=True)
    allow_customer_reschedule = Column(Boolean, default=True)
    require_cancel_reason = Column(Boolean, default=False)
    cancellation_policy_text = Column(Text)
    no_show_policy_text = Column(Text)
    no_show_limit_before_deposit_required = Column(Integer, default=2, nullable=False)
    auto_require_deposit_after_no_show = Column(Boolean, default=False, nullable=False)
    consume_package_session_on_no_show = Column(Boolean, default=False, nullable=False)

    tenant = relationship("Tenant", back_populates="booking_policy")


class TenantPaymentSettings(Base, UUIDPrimaryKey, TimestampMixin):
    """Manual Pix/deposit payment settings per tenant."""
    __tablename__ = "tenant_payment_settings"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    require_deposit_by_default = Column(Boolean, default=False, nullable=False)
    default_deposit_type = Column(String(20), default="none", nullable=False)
    default_deposit_value = Column(Numeric(10, 2), default=0, nullable=False)
    require_deposit_for_first_appointment = Column(Boolean, default=False, nullable=False)
    require_deposit_after_no_show = Column(Boolean, default=False, nullable=False)
    manual_payment_instructions = Column(Text, nullable=True)
    pix_key = Column(String(255), nullable=True)

    tenant = relationship("Tenant", back_populates="payment_settings")

    __table_args__ = (
        CheckConstraint("default_deposit_type IN ('none','fixed','percentage')", name="ck_tenant_payment_settings_deposit_type"),
        CheckConstraint("default_deposit_value >= 0", name="ck_tenant_payment_settings_deposit_value_non_negative"),
    )
