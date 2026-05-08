"""add support tickets

Revision ID: 0014_add_support_tickets
Revises: 0013_add_platform_settings
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0014_add_support_tickets"
down_revision = "0013_add_platform_settings"
branch_labels = None
depends_on = None


SUPPORT_TICKET_CATEGORY_ENUM = postgresql.ENUM(
    "bug", "question", "billing", "feature_request", "other",
    name="support_ticket_category",
    create_type=False,
)
SUPPORT_TICKET_PRIORITY_ENUM = postgresql.ENUM(
    "low", "normal", "high", "urgent",
    name="support_ticket_priority",
    create_type=False,
)
SUPPORT_TICKET_STATUS_ENUM = postgresql.ENUM(
    "open", "pending", "resolved", "closed",
    name="support_ticket_status",
    create_type=False,
)


def upgrade() -> None:
    SUPPORT_TICKET_CATEGORY_ENUM.create(op.get_bind(), checkfirst=True)
    SUPPORT_TICKET_PRIORITY_ENUM.create(op.get_bind(), checkfirst=True)
    SUPPORT_TICKET_STATUS_ENUM.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "support_tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("category", SUPPORT_TICKET_CATEGORY_ENUM,
                  nullable=False, server_default="question"),
        sa.Column("priority", SUPPORT_TICKET_PRIORITY_ENUM,
                  nullable=False, server_default="normal"),
        sa.Column("status", SUPPORT_TICKET_STATUS_ENUM,
                  nullable=False, server_default="open"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_support_tickets_tenant_id", "support_tickets", ["tenant_id"])
    op.create_index("ix_support_tickets_created_by_user_id", "support_tickets", ["created_by_user_id"])
    op.create_index("ix_support_tickets_assigned_to_user_id", "support_tickets", ["assigned_to_user_id"])
    op.create_index("ix_support_tickets_status", "support_tickets", ["status"])
    op.create_index("ix_support_tickets_tenant_status", "support_tickets", ["tenant_id", "status"])

    op.create_table(
        "support_ticket_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("author_side", sa.String(20), nullable=False, server_default="tenant"),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_support_ticket_messages_ticket_id", "support_ticket_messages", ["ticket_id"])
    op.create_index("ix_support_ticket_messages_author_user_id", "support_ticket_messages", ["author_user_id"])


def downgrade() -> None:
    op.drop_table("support_ticket_messages")
    op.drop_table("support_tickets")
    SUPPORT_TICKET_STATUS_ENUM.drop(op.get_bind(), checkfirst=True)
    SUPPORT_TICKET_PRIORITY_ENUM.drop(op.get_bind(), checkfirst=True)
    SUPPORT_TICKET_CATEGORY_ENUM.drop(op.get_bind(), checkfirst=True)
