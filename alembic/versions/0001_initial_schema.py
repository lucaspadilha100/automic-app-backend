"""initial schema — all tables

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── plans ──────────────────────────────────────────────────────────────────
    op.create_table(
        "plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text),
        sa.Column("price_monthly", sa.Numeric(10, 2), default=0),
        sa.Column("max_services", sa.Integer, nullable=True),
        sa.Column("max_professionals", sa.Integer, nullable=True),
        sa.Column("max_users", sa.Integer, nullable=True),
        sa.Column("max_appointments_per_month", sa.Integer, nullable=True),
        sa.Column("max_units", sa.Integer, default=1),
        sa.Column("max_packages", sa.Integer, nullable=True),
        sa.Column("allow_online_payment", sa.Boolean, default=False),
        sa.Column("allow_packages", sa.Boolean, default=True),
        sa.Column("allow_custom_terms", sa.Boolean, default=False),
        sa.Column("allow_advanced_reports", sa.Boolean, default=False),
        sa.Column("allow_crm_integration", sa.Boolean, default=False),
        sa.Column("allow_before_after_photos", sa.Boolean, default=False),
        sa.Column("allow_multi_unit", sa.Boolean, default=False),
        sa.Column("allow_waitlist", sa.Boolean, default=False),
        sa.Column("allow_physical_resources", sa.Boolean, default=False),
        sa.Column("allow_webhooks", sa.Boolean, default=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── tenants ────────────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, default="trial"),
        sa.Column("public_name", sa.String(200)),
        sa.Column("short_description", sa.Text),
        sa.Column("category", sa.String(100)),
        sa.Column("phone", sa.String(30)),
        sa.Column("whatsapp", sa.String(30)),
        sa.Column("email", sa.String(200)),
        sa.Column("address", sa.Text),
        sa.Column("instagram", sa.String(200)),
        sa.Column("website", sa.String(300)),
        sa.Column("custom_domain", sa.String(300)),
        sa.Column("custom_domain_enabled", sa.Boolean, default=False),
        sa.Column("timezone", sa.String(60), default="America/Sao_Paulo", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('trial','active','suspended','cancelled','inactive')",
            name="ck_tenants_status",
        ),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"])

    # ── tenant_subscriptions ───────────────────────────────────────────────────
    op.create_table(
        "tenant_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="trial"),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('trial','active','suspended','cancelled','past_due')",
            name="ck_tenant_subscriptions_status",
        ),
    )
    op.create_index("ix_tenant_subscriptions_tenant_id", "tenant_subscriptions", ["tenant_id"])

    # ── tenant_limit_overrides ─────────────────────────────────────────────────
    op.create_table(
        "tenant_limit_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("max_services", sa.Integer),
        sa.Column("max_professionals", sa.Integer),
        sa.Column("max_users", sa.Integer),
        sa.Column("max_appointments_per_month", sa.Integer),
        sa.Column("max_units", sa.Integer),
        sa.Column("max_packages", sa.Integer),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── tenant_feature_flags ───────────────────────────────────────────────────
    op.create_table(
        "tenant_feature_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feature_key", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, default=True),
        sa.Column("source", sa.String(20), default="plan"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "feature_key", name="uq_tenant_feature_flags_tenant_id_feature_key"),
    )
    op.create_index("ix_tenant_feature_flags_tenant_id", "tenant_feature_flags", ["tenant_id"])

    # ── tenant_settings ────────────────────────────────────────────────────────
    op.create_table(
        "tenant_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("show_prices", sa.Boolean, default=True),
        sa.Column("show_duration", sa.Boolean, default=True),
        sa.Column("show_professionals", sa.Boolean, default=True),
        sa.Column("allow_professional_choice", sa.Boolean, default=True),
        sa.Column("allow_any_professional", sa.Boolean, default=True),
        sa.Column("allow_multiple_services", sa.Boolean, default=True),
        sa.Column("allow_customer_cancel", sa.Boolean, default=True),
        sa.Column("allow_customer_reschedule", sa.Boolean, default=True),
        sa.Column("require_customer_cpf", sa.Boolean, default=False),
        sa.Column("require_customer_birth_date", sa.Boolean, default=False),
        sa.Column("require_terms_acceptance", sa.Boolean, default=False),
        sa.Column("require_deposit_payment", sa.Boolean, default=False),
        sa.Column("allow_online_payment", sa.Boolean, default=False),
        sa.Column("show_instagram", sa.Boolean, default=True),
        sa.Column("show_whatsapp", sa.Boolean, default=True),
        sa.Column("show_address", sa.Boolean, default=True),
        sa.Column("homepage_title", sa.String(300)),
        sa.Column("homepage_subtitle", sa.Text),
        sa.Column("primary_button_text", sa.String(100)),
        sa.Column("confirmation_message", sa.Text),
        sa.Column("cancellation_message", sa.Text),
        sa.Column("payment_pending_message", sa.Text),
        sa.Column("footer_text", sa.Text),
        sa.Column("terms_text", sa.Text),
        sa.Column("privacy_text", sa.Text),
        sa.Column("no_show_policy_text", sa.Text),
        sa.Column("cancellation_policy_text", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── tenant_themes ──────────────────────────────────────────────────────────
    op.create_table(
        "tenant_themes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("logo_url", sa.String(500)),
        sa.Column("logo_small_url", sa.String(500)),
        sa.Column("favicon_url", sa.String(500)),
        sa.Column("cover_image_url", sa.String(500)),
        sa.Column("primary_color", sa.String(20)),
        sa.Column("secondary_color", sa.String(20)),
        sa.Column("background_color", sa.String(20)),
        sa.Column("button_color", sa.String(20)),
        sa.Column("text_color", sa.String(20)),
        sa.Column("font_family", sa.String(100)),
        sa.Column("visual_style", sa.String(50)),
        sa.Column("theme_preset", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── tenant_booking_policies ────────────────────────────────────────────────
    op.create_table(
        "tenant_booking_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("min_minutes_before_booking", sa.Integer, default=60),
        sa.Column("max_days_ahead_booking", sa.Integer, default=60),
        sa.Column("slot_interval_minutes", sa.Integer, default=30),
        sa.Column("min_hours_before_cancel", sa.Integer, default=24),
        sa.Column("min_hours_before_reschedule", sa.Integer, default=24),
        sa.Column("allow_customer_cancel", sa.Boolean, default=True),
        sa.Column("allow_customer_reschedule", sa.Boolean, default=True),
        sa.Column("require_cancel_reason", sa.Boolean, default=False),
        sa.Column("cancellation_policy_text", sa.Text),
        sa.Column("no_show_policy_text", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── customer_accounts ──────────────────────────────────────────────────────
    op.create_table(
        "customer_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(255), unique=True),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True)),
        sa.Column("phone_verified_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_customer_accounts_email", "customer_accounts", ["email"])
    op.create_index("ix_customer_accounts_phone", "customer_accounts", ["phone"])

    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(30)),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_id_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ── password_reset_tokens ──────────────────────────────────────────────────
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("customer_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customer_accounts.id", ondelete="CASCADE")),
        sa.Column("token", sa.String(200), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_password_reset_tokens_token", "password_reset_tokens", ["token"])

    # ── user_invites ───────────────────────────────────────────────────────────
    op.create_table(
        "user_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(30)),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("invited_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token", sa.String(200), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_invites_tenant_id", "user_invites", ["tenant_id"])
    op.create_index("ix_user_invites_token", "user_invites", ["token"])

    # ── service_categories ─────────────────────────────────────────────────────
    op.create_table(
        "service_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("sort_order", sa.Integer, default=0),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_service_categories_tenant_name"),
    )
    op.create_index("ix_service_categories_tenant_id", "service_categories", ["tenant_id"])

    # ── services ───────────────────────────────────────────────────────────────
    op.create_table(
        "services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("service_categories.id")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("price", sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column("duration_minutes", sa.Integer, nullable=False),
        sa.Column("buffer_before_minutes", sa.Integer, default=0, nullable=False),
        sa.Column("buffer_after_minutes", sa.Integer, default=0, nullable=False),
        sa.Column("image_url", sa.String(500)),
        sa.Column("requires_deposit", sa.Boolean, default=False),
        sa.Column("deposit_type", sa.String(20), default="none"),
        sa.Column("deposit_value", sa.Numeric(10, 2), default=0),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("price >= 0", name="ck_services_price_non_negative"),
        sa.CheckConstraint("duration_minutes > 0", name="ck_services_duration_positive"),
        sa.CheckConstraint("buffer_before_minutes >= 0", name="ck_services_buffer_before_non_negative"),
        sa.CheckConstraint("buffer_after_minutes >= 0", name="ck_services_buffer_after_non_negative"),
        sa.CheckConstraint("deposit_value >= 0", name="ck_services_deposit_value_non_negative"),
        sa.CheckConstraint("deposit_type IN ('none','fixed','percentage')", name="ck_services_deposit_type"),
    )
    op.create_index("ix_services_tenant_id", "services", ["tenant_id"])

    # ── professionals ──────────────────────────────────────────────────────────
    op.create_table(
        "professionals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("bio", sa.Text),
        sa.Column("photo_url", sa.String(500)),
        sa.Column("phone", sa.String(30)),
        sa.Column("email", sa.String(255)),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_professionals_tenant_id", "professionals", ["tenant_id"])

    # ── professional_services ──────────────────────────────────────────────────
    op.create_table(
        "professional_services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("services.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "professional_id", "service_id", name="uq_professional_services"),
    )

    # ── professional_availability ──────────────────────────────────────────────
    op.create_table(
        "professional_availability",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weekday", sa.Integer, nullable=False),
        sa.Column("start_time", sa.Time),
        sa.Column("end_time", sa.Time),
        sa.Column("break_start_time", sa.Time),
        sa.Column("break_end_time", sa.Time),
        sa.Column("is_available", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── business_hours ─────────────────────────────────────────────────────────
    op.create_table(
        "business_hours",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weekday", sa.Integer, nullable=False),
        sa.Column("open_time", sa.Time),
        sa.Column("close_time", sa.Time),
        sa.Column("break_start_time", sa.Time),
        sa.Column("break_end_time", sa.Time),
        sa.Column("is_closed", sa.Boolean, default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_business_hours_weekday"),
    )
    op.create_index("ix_business_hours_tenant_id", "business_hours", ["tenant_id"])

    # ── blocked_times ──────────────────────────────────────────────────────────
    op.create_table(
        "blocked_times",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("professionals.id", ondelete="CASCADE")),
        sa.Column("start_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("block_type", sa.String(30), nullable=False, default="other"),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("end_datetime > start_datetime", name="ck_blocked_times_datetime_order"),
        sa.CheckConstraint(
            "block_type IN ('tenant','professional','holiday','maintenance','personal','other')",
            name="ck_blocked_times_block_type",
        ),
    )
    op.create_index("ix_blocked_times_tenant_id", "blocked_times", ["tenant_id"])

    # ── units ──────────────────────────────────────────────────────────────────
    op.create_table(
        "units",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("address", sa.Text),
        sa.Column("phone", sa.String(30)),
        sa.Column("email", sa.String(255)),
        sa.Column("timezone", sa.String(60)),
        sa.Column("is_main", sa.Boolean, default=False, nullable=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_units_tenant_id", "units", ["tenant_id"])

    # ── packages ───────────────────────────────────────────────────────────────
    op.create_table(
        "packages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("total_sessions", sa.Integer, nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False, default=0),
        sa.Column("validity_days", sa.Integer),
        sa.Column("service_ids", postgresql.JSONB),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("total_sessions > 0", name="ck_packages_total_sessions_positive"),
        sa.CheckConstraint("price >= 0", name="ck_packages_price_non_negative"),
    )
    op.create_index("ix_packages_tenant_id", "packages", ["tenant_id"])

    # ── tenant_customers ───────────────────────────────────────────────────────
    op.create_table(
        "tenant_customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customer_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cpf", sa.String(20)),
        sa.Column("birth_date", sa.Date),
        sa.Column("notes", sa.Text),
        sa.Column("internal_notes", sa.Text),
        sa.Column("marketing_consent", sa.Boolean, default=False),
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True)),
        sa.Column("privacy_policy_accepted_at", sa.DateTime(timezone=True)),
        sa.Column("data_processing_consent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "customer_account_id", name="uq_tenant_customers_tenant_customer"),
    )
    op.create_index("ix_tenant_customers_tenant_id", "tenant_customers", ["tenant_id"])
    op.create_index("ix_tenant_customers_customer_account_id", "tenant_customers", ["customer_account_id"])

    # ── customer_tags ──────────────────────────────────────────────────────────
    op.create_table(
        "customer_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(20)),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_customer_tags_tenant_name"),
    )

    # ── customer_tag_links ─────────────────────────────────────────────────────
    op.create_table(
        "customer_tag_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant_customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customer_tags.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_customer_id", "tag_id", name="uq_customer_tag_links"),
    )

    # ── customer_notes ─────────────────────────────────────────────────────────
    op.create_table(
        "customer_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant_customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("is_internal", sa.Boolean, default=True),
        sa.Column("note_type", sa.String(50), default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── customer_packages ──────────────────────────────────────────────────────
    op.create_table(
        "customer_packages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customer_accounts.id"), nullable=False),
        sa.Column("tenant_customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant_customers.id"), nullable=False),
        sa.Column("package_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("packages.id"), nullable=False),
        sa.Column("total_sessions", sa.Integer, nullable=False),
        sa.Column("used_sessions", sa.Integer, nullable=False, default=0),
        sa.Column("remaining_sessions", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="active"),
        sa.Column("payment_status", sa.String(20), nullable=False, default="pending"),
        sa.Column("price_paid", sa.Numeric(10, 2)),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("remaining_sessions >= 0", name="ck_customer_packages_remaining_non_negative"),
        sa.CheckConstraint("used_sessions >= 0", name="ck_customer_packages_used_non_negative"),
        sa.CheckConstraint("status IN ('active','completed','expired','cancelled')", name="ck_customer_packages_status"),
        sa.CheckConstraint(
            "payment_status IN ('pending','paid','failed','refunded','cancelled')",
            name="ck_customer_packages_payment_status",
        ),
    )
    op.create_index("ix_customer_packages_tenant_id", "customer_packages", ["tenant_id"])
    op.create_index("ix_customer_packages_customer_account_id", "customer_packages", ["customer_account_id"])
    op.create_index("ix_customer_packages_tenant_customer_id", "customer_packages", ["tenant_customer_id"])

    # ── appointments ───────────────────────────────────────────────────────────
    op.create_table(
        "appointments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant_customers.id")),
        sa.Column("customer_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customer_accounts.id")),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("professionals.id"), nullable=False),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("units.id")),
        sa.Column("customer_package_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customer_packages.id")),
        sa.Column("start_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_duration_minutes", sa.Integer, nullable=False),
        sa.Column("total_price", sa.Numeric(10, 2), default=0),
        sa.Column("status", sa.String(30), nullable=False, default="scheduled"),
        sa.Column("payment_status", sa.String(20), nullable=False, default="not_required"),
        sa.Column("source", sa.String(30), default="admin_panel"),
        sa.Column("customer_notes", sa.Text),
        sa.Column("internal_notes", sa.Text),
        sa.Column("cancellation_reason", sa.Text),
        sa.Column("cancelled_by_type", sa.String(20)),
        sa.Column("cancelled_by_id", postgresql.UUID(as_uuid=True)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("no_show_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("end_datetime > start_datetime", name="ck_appointments_datetime_order"),
        sa.CheckConstraint("total_price >= 0", name="ck_appointments_price_non_negative"),
        sa.CheckConstraint(
            "status IN ('draft','pending_payment','scheduled','confirmed','in_progress','completed','cancelled','no_show','rescheduled')",
            name="ck_appointments_status",
        ),
        sa.CheckConstraint(
            "payment_status IN ('not_required','pending','paid','failed','refunded','cancelled')",
            name="ck_appointments_payment_status",
        ),
    )
    op.create_index("ix_appointments_tenant_id", "appointments", ["tenant_id"])
    op.create_index("ix_appointments_professional_id", "appointments", ["professional_id"])
    op.create_index("ix_appointments_start_datetime", "appointments", ["start_datetime"])
    op.create_index("ix_appointments_status", "appointments", ["status"])
    op.create_index("ix_appointments_customer_account_id", "appointments", ["customer_account_id"])
    op.create_index("ix_appointments_tenant_customer_id", "appointments", ["tenant_customer_id"])

    # ── appointment_services ───────────────────────────────────────────────────
    op.create_table(
        "appointment_services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("services.id")),
        sa.Column("service_name_snapshot", sa.String(200), nullable=False),
        sa.Column("service_price_snapshot", sa.Numeric(10, 2), nullable=False),
        sa.Column("service_duration_snapshot", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_appointment_services_tenant_id", "appointment_services", ["tenant_id"])
    op.create_index("ix_appointment_services_appointment_id", "appointment_services", ["appointment_id"])

    # ── appointment_status_history ─────────────────────────────────────────────
    op.create_table(
        "appointment_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(30)),
        sa.Column("to_status", sa.String(30), nullable=False),
        sa.Column("changed_by_type", sa.String(20)),
        sa.Column("changed_by_id", postgresql.UUID(as_uuid=True)),
        sa.Column("reason", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_appointment_status_history_tenant_id", "appointment_status_history", ["tenant_id"])
    op.create_index("ix_appointment_status_history_appointment_id", "appointment_status_history", ["appointment_id"])

    # ── idempotency_keys ───────────────────────────────────────────────────────
    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customer_accounts.id")),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64)),
        sa.Column("response_body", postgresql.JSONB),
        sa.Column("status", sa.String(20), default="processing"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "key", name="uq_idempotency_keys_tenant_key"),
    )

    # ── payments ───────────────────────────────────────────────────────────────
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customer_accounts.id")),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="pending"),
        sa.Column("payment_method", sa.String(30), default="none"),
        sa.Column("provider", sa.String(50)),
        sa.Column("provider_payment_id", sa.String(200)),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount >= 0", name="ck_payments_amount_non_negative"),
        sa.CheckConstraint("status IN ('pending','paid','failed','refunded','cancelled')", name="ck_payments_status"),
        sa.CheckConstraint(
            "payment_method IN ('none','pix_manual','pix_gateway','credit_card','debit_card','cash','other')",
            name="ck_payments_method",
        ),
    )
    op.create_index("ix_payments_tenant_id", "payments", ["tenant_id"])
    op.create_index("ix_payments_appointment_id", "payments", ["appointment_id"])

    # ── package_sessions ───────────────────────────────────────────────────────
    op.create_table(
        "package_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_package_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customer_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("appointments.id")),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("services.id")),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("action IN ('reserved','consumed','returned','cancelled')", name="ck_package_sessions_action"),
    )
    op.create_index("ix_package_sessions_tenant_id", "package_sessions", ["tenant_id"])
    op.create_index("ix_package_sessions_customer_package_id", "package_sessions", ["customer_package_id"])

    # ── procedure_history ──────────────────────────────────────────────────────
    op.create_table(
        "procedure_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant_customers.id"), nullable=False),
        sa.Column("customer_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customer_accounts.id")),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("appointments.id")),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("professionals.id")),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("services.id")),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("procedure_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("public_notes", sa.Text),
        sa.Column("internal_notes", sa.Text),
        sa.Column("recommended_return_date", sa.Date),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_procedure_history_tenant_id", "procedure_history", ["tenant_id"])
    op.create_index("ix_procedure_history_tenant_customer_id", "procedure_history", ["tenant_customer_id"])

    # ── customer_events ────────────────────────────────────────────────────────
    op.create_table(
        "customer_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customer_accounts.id")),
        sa.Column("tenant_customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant_customers.id")),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True)),
        sa.Column("metadata", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_customer_events_tenant_id", "customer_events", ["tenant_id"])
    op.create_index("ix_customer_events_customer_account_id", "customer_events", ["customer_account_id"])
    op.create_index("ix_customer_events_event_type", "customer_events", ["event_type"])

    # ── audit_logs ─────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="SET NULL")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("customer_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customer_accounts.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(80)),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True)),
        sa.Column("old_values", postgresql.JSONB),
        sa.Column("new_values", postgresql.JSONB),
        sa.Column("ip_address", sa.String(50)),
        sa.Column("user_agent", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # ── notification_templates ─────────────────────────────────────────────────
    op.create_table(
        "notification_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("subject", sa.String(300)),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("channel IN ('whatsapp','email','sms','internal')", name="ck_notif_templates_channel"),
    )

    # ── notification_logs ──────────────────────────────────────────────────────
    op.create_table(
        "notification_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customer_accounts.id")),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("appointments.id")),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="pending"),
        sa.Column("provider", sa.String(50)),
        sa.Column("error_message", sa.Text),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notification_logs_tenant_id", "notification_logs", ["tenant_id"])
    op.create_index("ix_notification_logs_event_type", "notification_logs", ["event_type"])
    op.create_index("ix_notification_logs_status", "notification_logs", ["status"])

    # ── webhook_endpoints ──────────────────────────────────────────────────────
    op.create_table(
        "webhook_endpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("secret", sa.String(200)),
        sa.Column("event_types", postgresql.JSONB),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_webhook_endpoints_tenant_id", "webhook_endpoints", ["tenant_id"])

    # ── webhook_deliveries ─────────────────────────────────────────────────────
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("webhook_endpoint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("webhook_endpoints.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("payload", postgresql.JSONB),
        sa.Column("status", sa.String(20), nullable=False, default="pending"),
        sa.Column("response_status", sa.Integer),
        sa.Column("response_body", sa.Text),
        sa.Column("attempt_count", sa.Integer, default=0),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_webhook_deliveries_tenant_id", "webhook_deliveries", ["tenant_id"])
    op.create_index("ix_webhook_deliveries_status", "webhook_deliveries", ["status"])

    # ── media_files ────────────────────────────────────────────────────────────
    op.create_table(
        "media_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("file_url", sa.String(1000), nullable=False),
        sa.Column("file_type", sa.String(50)),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True)),
        sa.Column("original_filename", sa.String(300)),
        sa.Column("mime_type", sa.String(100)),
        sa.Column("size_bytes", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_media_files_tenant_id", "media_files", ["tenant_id"])

    # ── resources ──────────────────────────────────────────────────────────────
    op.create_table(
        "resources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("type", sa.String(30), default="other"),
        sa.Column("description", sa.Text),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── service_resources ──────────────────────────────────────────────────────
    op.create_table(
        "service_resources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("services.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── appointment_resources ──────────────────────────────────────────────────
    op.create_table(
        "appointment_resources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── waitlist_entries ───────────────────────────────────────────────────────
    op.create_table(
        "waitlist_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customer_accounts.id"), nullable=False),
        sa.Column("tenant_customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant_customers.id")),
        sa.Column("service_ids", postgresql.JSONB),
        sa.Column("preferred_professional_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("professionals.id")),
        sa.Column("preferred_date", sa.Date),
        sa.Column("preferred_period", sa.String(20)),
        sa.Column("status", sa.String(20), nullable=False, default="waiting"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('waiting','notified','converted','cancelled')", name="ck_waitlist_status"),
    )
    op.create_index("ix_waitlist_entries_tenant_id", "waitlist_entries", ["tenant_id"])
    op.create_index("ix_waitlist_entries_customer_account_id", "waitlist_entries", ["customer_account_id"])


def downgrade() -> None:
    # Drop in reverse dependency order
    tables = [
        "waitlist_entries", "appointment_resources", "service_resources", "resources",
        "media_files", "webhook_deliveries", "webhook_endpoints",
        "notification_logs", "notification_templates", "audit_logs",
        "customer_events", "procedure_history", "package_sessions",
        "payments", "idempotency_keys", "appointment_status_history",
        "appointment_services", "appointments", "customer_packages",
        "customer_notes", "customer_tag_links", "customer_tags",
        "tenant_customers", "units", "blocked_times", "business_hours",
        "professional_availability", "professional_services",
        "professionals", "services", "service_categories",
        "user_invites", "password_reset_tokens", "users",
        "customer_accounts", "tenant_booking_policies", "tenant_themes",
        "tenant_settings", "tenant_feature_flags", "tenant_limit_overrides",
        "tenant_subscriptions", "tenants", "plans",
    ]
    for t in tables:
        op.drop_table(t)
