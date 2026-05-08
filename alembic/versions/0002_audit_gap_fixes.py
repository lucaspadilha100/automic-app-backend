"""audit gap fixes: payment settings, package services, customer portal support

Revision ID: 0002_audit_gap_fixes
Revises: 0001_initial_schema
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_audit_gap_fixes"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_payment_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("require_deposit_by_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_deposit_type", sa.String(length=20), nullable=False, server_default="none"),
        sa.Column("default_deposit_value", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("require_deposit_for_first_appointment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("require_deposit_after_no_show", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("manual_payment_instructions", sa.Text(), nullable=True),
        sa.Column("pix_key", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("default_deposit_type IN ('none','fixed','percentage')", name="ck_tenant_payment_settings_deposit_type"),
        sa.CheckConstraint("default_deposit_value >= 0", name="ck_tenant_payment_settings_deposit_value_non_negative"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_payment_settings_tenant_id"),
    )
    op.create_index("ix_tenant_payment_settings_tenant_id", "tenant_payment_settings", ["tenant_id"])

    op.add_column("tenant_booking_policies", sa.Column("no_show_limit_before_deposit_required", sa.Integer(), nullable=False, server_default="2"))
    op.add_column("tenant_booking_policies", sa.Column("auto_require_deposit_after_no_show", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("tenant_booking_policies", sa.Column("consume_package_session_on_no_show", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_table(
        "package_services",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("package_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["package_id"], ["packages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "package_id", "service_id", name="uq_package_services_tenant_package_service"),
    )
    op.create_index("ix_package_services_tenant_id", "package_services", ["tenant_id"])
    op.create_index("ix_package_services_package_id", "package_services", ["package_id"])
    op.create_index("ix_package_services_service_id", "package_services", ["service_id"])

    op.add_column("appointments", sa.Column("uses_package", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("appointment_services", sa.Column("package_session_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_appointment_services_package_session_id_package_sessions", "appointment_services", "package_sessions", ["package_session_id"], ["id"])
    op.add_column("units", sa.Column("whatsapp", sa.String(length=30), nullable=True))

    op.create_table(
        "appointment_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(length=30), nullable=False, server_default="customer_visible"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_appointment_reviews_rating_range"),
        sa.CheckConstraint("visibility IN ('internal','public','customer_visible')", name="ck_appointment_reviews_visibility"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_account_id"], ["customer_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_appointment_reviews_tenant_id", "appointment_reviews", ["tenant_id"])
    op.create_index("ix_appointment_reviews_appointment_id", "appointment_reviews", ["appointment_id"])
    op.create_index("ix_appointment_reviews_customer_account_id", "appointment_reviews", ["customer_account_id"])

    op.create_table(
        "coupons",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("discount_type", sa.String(length=20), nullable=False),
        sa.Column("discount_value", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_limit", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("discount_type IN ('fixed','percentage')", name="ck_coupons_discount_type"),
        sa.CheckConstraint("discount_value >= 0", name="ck_coupons_discount_value_non_negative"),
        sa.CheckConstraint("usage_limit IS NULL OR usage_limit >= 0", name="ck_coupons_usage_limit_non_negative"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_coupons_tenant_code"),
    )
    op.create_index("ix_coupons_tenant_id", "coupons", ["tenant_id"])

    op.create_table(
        "appointment_holds",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("service_ids", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("end_datetime > start_datetime", name="ck_appointment_holds_datetime_order"),
        sa.CheckConstraint("status IN ('active','expired','converted','cancelled')", name="ck_appointment_holds_status"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_account_id"], ["customer_accounts.id"]),
        sa.ForeignKeyConstraint(["professional_id"], ["professionals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_appointment_holds_tenant_id", "appointment_holds", ["tenant_id"])
    op.create_index("ix_appointment_holds_customer_account_id", "appointment_holds", ["customer_account_id"])
    op.create_index("ix_appointment_holds_professional_id", "appointment_holds", ["professional_id"])
    op.create_index("ix_appointment_holds_start_datetime", "appointment_holds", ["start_datetime"])
    op.create_index("ix_appointment_holds_end_datetime", "appointment_holds", ["end_datetime"])


def downgrade() -> None:
    op.drop_index("ix_appointment_holds_end_datetime", table_name="appointment_holds")
    op.drop_index("ix_appointment_holds_start_datetime", table_name="appointment_holds")
    op.drop_index("ix_appointment_holds_professional_id", table_name="appointment_holds")
    op.drop_index("ix_appointment_holds_customer_account_id", table_name="appointment_holds")
    op.drop_index("ix_appointment_holds_tenant_id", table_name="appointment_holds")
    op.drop_table("appointment_holds")
    op.drop_index("ix_coupons_tenant_id", table_name="coupons")
    op.drop_table("coupons")
    op.drop_index("ix_appointment_reviews_customer_account_id", table_name="appointment_reviews")
    op.drop_index("ix_appointment_reviews_appointment_id", table_name="appointment_reviews")
    op.drop_index("ix_appointment_reviews_tenant_id", table_name="appointment_reviews")
    op.drop_table("appointment_reviews")
    op.drop_column("units", "whatsapp")
    op.drop_constraint("fk_appointment_services_package_session_id_package_sessions", "appointment_services", type_="foreignkey")
    op.drop_column("appointment_services", "package_session_id")
    op.drop_column("appointments", "uses_package")
    op.drop_index("ix_package_services_service_id", table_name="package_services")
    op.drop_index("ix_package_services_package_id", table_name="package_services")
    op.drop_index("ix_package_services_tenant_id", table_name="package_services")
    op.drop_table("package_services")
    op.drop_column("tenant_booking_policies", "consume_package_session_on_no_show")
    op.drop_column("tenant_booking_policies", "auto_require_deposit_after_no_show")
    op.drop_column("tenant_booking_policies", "no_show_limit_before_deposit_required")
    op.drop_index("ix_tenant_payment_settings_tenant_id", table_name="tenant_payment_settings")
    op.drop_table("tenant_payment_settings")
