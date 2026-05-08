"""add platform settings

Revision ID: 0013_add_platform_settings
Revises: 0012_add_commercial_overrides_and_mrr
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0013_add_platform_settings"
down_revision = "0012_add_commercial_overrides_and_mrr"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("is_singleton", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        # Identity
        sa.Column("platform_name", sa.String(100), nullable=False, server_default="AUTOMIC"),
        sa.Column("platform_tagline", sa.String(255), nullable=True),
        sa.Column("platform_legal_name", sa.String(255), nullable=True),
        sa.Column("platform_cnpj", sa.String(20), nullable=True),
        # Branding
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("logo_dark_url", sa.String(500), nullable=True),
        sa.Column("favicon_url", sa.String(500), nullable=True),
        sa.Column("primary_color", sa.String(20), nullable=False, server_default="#22D3EE"),
        sa.Column("secondary_color", sa.String(20), nullable=False, server_default="#0F172A"),
        sa.Column("accent_color", sa.String(20), nullable=True, server_default="#06B6D4"),
        # Contact / Support
        sa.Column("support_email", sa.String(255), nullable=True),
        sa.Column("support_phone", sa.String(30), nullable=True),
        sa.Column("support_url", sa.String(500), nullable=True),
        sa.Column("sales_email", sa.String(255), nullable=True),
        sa.Column("sales_phone", sa.String(30), nullable=True),
        # Domain / Marketing
        sa.Column("primary_domain", sa.String(255), nullable=True),
        sa.Column("marketing_url", sa.String(500), nullable=True),
        sa.Column("instagram_url", sa.String(500), nullable=True),
        sa.Column("linkedin_url", sa.String(500), nullable=True),
        # Legal
        sa.Column("terms_of_service_url", sa.String(500), nullable=True),
        sa.Column("privacy_policy_url", sa.String(500), nullable=True),
        # Notifications to owner
        sa.Column("owner_notification_emails", sa.Text(), nullable=True),
        # Free-form
        sa.Column("notes", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("is_singleton", name="uq_platform_settings_singleton"),
    )


def downgrade() -> None:
    op.drop_table("platform_settings")
