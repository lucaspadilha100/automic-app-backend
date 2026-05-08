"""add whatsapp settings

Revision ID: 0011_add_whatsapp_settings
Revises: 0010_add_automation_rules
Create Date: 2026-05-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011_add_whatsapp_settings"
down_revision = "0010_add_automation_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add allow_whatsapp_integration to plans
    op.add_column("plans", sa.Column(
        "allow_whatsapp_integration", sa.Boolean(),
        nullable=True, server_default=sa.text("false"),
    ))

    op.create_table(
        "tenant_whatsapp_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("connection_type", sa.String(50), nullable=True),
        sa.Column("webhook_url", sa.String(1000), nullable=True),
        sa.Column("instance_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="disconnected"),
        sa.Column("last_connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('disconnected','connected','waiting_qr','error')",
            name="ck_tenant_whatsapp_settings_status",
        ),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_whatsapp_settings_tenant"),
    )
    op.create_index("ix_tenant_whatsapp_settings_tenant_id", "tenant_whatsapp_settings", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("tenant_whatsapp_settings")
    op.drop_column("plans", "allow_whatsapp_integration")
