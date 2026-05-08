"""add owner notifications

Revision ID: 0015_add_owner_notifications
Revises: 0014_add_support_tickets
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0015_add_owner_notifications"
down_revision = "0014_add_support_tickets"
branch_labels = None
depends_on = None


OWNER_NOTIFICATION_TYPE_ENUM = postgresql.ENUM(
    "tenant_signup", "tenant_cancelled", "tenant_suspended", "tenant_reactivated",
    "tenant_payment_failed", "support_ticket_created", "support_ticket_replied",
    "custom",
    name="owner_notification_type",
    create_type=False,
)
OWNER_NOTIFICATION_SEVERITY_ENUM = postgresql.ENUM(
    "info", "success", "warning", "error",
    name="owner_notification_severity",
    create_type=False,
)


def upgrade() -> None:
    OWNER_NOTIFICATION_TYPE_ENUM.create(op.get_bind(), checkfirst=True)
    OWNER_NOTIFICATION_SEVERITY_ENUM.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "owner_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("notification_type", OWNER_NOTIFICATION_TYPE_ENUM, nullable=False),
        sa.Column("severity", OWNER_NOTIFICATION_SEVERITY_ENUM,
                  nullable=False, server_default="info"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("related_entity_type", sa.String(50), nullable=True),
        sa.Column("related_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_owner_notifications_notification_type", "owner_notifications",
                    ["notification_type"])
    op.create_index("ix_owner_notifications_tenant_id", "owner_notifications", ["tenant_id"])
    op.create_index("ix_owner_notifications_is_read", "owner_notifications", ["is_read"])
    op.create_index("ix_owner_notifications_created_at", "owner_notifications", ["created_at"])
    op.create_index("ix_owner_notifications_unread", "owner_notifications",
                    ["is_read", "created_at"])


def downgrade() -> None:
    op.drop_table("owner_notifications")
    OWNER_NOTIFICATION_SEVERITY_ENUM.drop(op.get_bind(), checkfirst=True)
    OWNER_NOTIFICATION_TYPE_ENUM.drop(op.get_bind(), checkfirst=True)
