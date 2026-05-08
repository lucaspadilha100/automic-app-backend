"""prompt alignment fixes: safe portal, package status aliases, units and presets

Revision ID: 0003_prompt_alignment_fixes
Revises: 0002_audit_gap_fixes
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_prompt_alignment_fixes"
down_revision = "0002_audit_gap_fixes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Multi-unit relationships requested by the prompt.
    op.add_column("professionals", sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_professionals_unit_id", "professionals", ["unit_id"])
    op.create_foreign_key("fk_professionals_unit_id_units", "professionals", "units", ["unit_id"], ["id"])

    op.add_column("resources", sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_resources_unit_id", "resources", ["unit_id"])
    op.create_foreign_key("fk_resources_unit_id_units", "resources", "units", ["unit_id"], ["id"])

    op.add_column("business_hours", sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_business_hours_unit_id", "business_hours", ["unit_id"])
    op.create_foreign_key("fk_business_hours_unit_id_units", "business_hours", "units", ["unit_id"], ["id"])

    # Prompt-compatible tenant_customer_tags shape while keeping existing customer_tag_links table.
    op.add_column("customer_tag_links", sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_customer_tag_links_tenant_id", "customer_tag_links", ["tenant_id"])
    op.create_foreign_key("fk_customer_tag_links_tenant_id_tenants", "customer_tag_links", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE")

    # Prompt-compatible note/visibility aliases while keeping legacy content/is_internal fields.
    op.add_column("customer_notes", sa.Column("note", sa.Text(), nullable=True))
    op.add_column("customer_notes", sa.Column("visibility", sa.String(length=30), nullable=True, server_default="internal"))

    # Prompt-compatible status-history names while keeping existing names.
    op.add_column("appointment_status_history", sa.Column("old_status", sa.String(length=30), nullable=True))
    op.add_column("appointment_status_history", sa.Column("new_status", sa.String(length=30), nullable=True))
    op.add_column("appointment_status_history", sa.Column("changed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("appointment_status_history", sa.Column("changed_by_customer_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_appointment_status_history_changed_by_user_id", "appointment_status_history", "users", ["changed_by_user_id"], ["id"])
    op.create_foreign_key("fk_appointment_status_history_changed_by_customer_id", "appointment_status_history", "customer_accounts", ["changed_by_customer_id"], ["id"])

    # Package prompt names and statuses.
    op.add_column("customer_packages", sa.Column("purchase_price", sa.Numeric(10, 2), nullable=True))
    op.add_column("customer_packages", sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_customer_packages_created_by_user_id", "customer_packages", "users", ["created_by_user_id"], ["id"])
    op.drop_constraint("ck_customer_packages_status", "customer_packages", type_="check")
    op.create_check_constraint("ck_customer_packages_status", "customer_packages", "status IN ('active','fully_used','completed','expired','cancelled')")
    op.drop_constraint("ck_customer_packages_payment_status", "customer_packages", type_="check")
    op.create_check_constraint("ck_customer_packages_payment_status", "customer_packages", "payment_status IN ('pending','paid','partially_paid','failed','refunded','cancelled')")

    op.add_column("package_sessions", sa.Column("status", sa.String(length=20), nullable=True))
    op.create_check_constraint("ck_package_sessions_status", "package_sessions", "status IS NULL OR status IN ('reserved','used','cancelled')")

    # Global white-label theme presets.
    op.create_table(
        "theme_presets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("primary_color", sa.String(length=20), nullable=True),
        sa.Column("secondary_color", sa.String(length=20), nullable=True),
        sa.Column("background_color", sa.String(length=20), nullable=True),
        sa.Column("button_color", sa.String(length=20), nullable=True),
        sa.Column("text_color", sa.String(length=20), nullable=True),
        sa.Column("font_family", sa.String(length=100), nullable=True),
        sa.Column("visual_style", sa.String(length=50), nullable=True),
        sa.Column("default_texts", postgresql.JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_theme_presets_key"),
    )
    op.create_index("ix_theme_presets_key", "theme_presets", ["key"])


def downgrade() -> None:
    op.drop_index("ix_theme_presets_key", table_name="theme_presets")
    op.drop_table("theme_presets")

    op.drop_constraint("ck_package_sessions_status", "package_sessions", type_="check")
    op.drop_column("package_sessions", "status")

    op.drop_constraint("ck_customer_packages_payment_status", "customer_packages", type_="check")
    op.create_check_constraint("ck_customer_packages_payment_status", "customer_packages", "payment_status IN ('pending','paid','failed','refunded','cancelled')")
    op.drop_constraint("ck_customer_packages_status", "customer_packages", type_="check")
    op.create_check_constraint("ck_customer_packages_status", "customer_packages", "status IN ('active','completed','expired','cancelled')")
    op.drop_constraint("fk_customer_packages_created_by_user_id", "customer_packages", type_="foreignkey")
    op.drop_column("customer_packages", "created_by_user_id")
    op.drop_column("customer_packages", "purchase_price")

    op.drop_constraint("fk_appointment_status_history_changed_by_customer_id", "appointment_status_history", type_="foreignkey")
    op.drop_constraint("fk_appointment_status_history_changed_by_user_id", "appointment_status_history", type_="foreignkey")
    op.drop_column("appointment_status_history", "changed_by_customer_id")
    op.drop_column("appointment_status_history", "changed_by_user_id")
    op.drop_column("appointment_status_history", "new_status")
    op.drop_column("appointment_status_history", "old_status")

    op.drop_column("customer_notes", "visibility")
    op.drop_column("customer_notes", "note")

    op.drop_constraint("fk_customer_tag_links_tenant_id_tenants", "customer_tag_links", type_="foreignkey")
    op.drop_index("ix_customer_tag_links_tenant_id", table_name="customer_tag_links")
    op.drop_column("customer_tag_links", "tenant_id")

    op.drop_constraint("fk_business_hours_unit_id_units", "business_hours", type_="foreignkey")
    op.drop_index("ix_business_hours_unit_id", table_name="business_hours")
    op.drop_column("business_hours", "unit_id")
    op.drop_constraint("fk_resources_unit_id_units", "resources", type_="foreignkey")
    op.drop_index("ix_resources_unit_id", table_name="resources")
    op.drop_column("resources", "unit_id")
    op.drop_constraint("fk_professionals_unit_id_units", "professionals", type_="foreignkey")
    op.drop_index("ix_professionals_unit_id", table_name="professionals")
    op.drop_column("professionals", "unit_id")
