"""add automation rules

Revision ID: 0010_add_automation_rules
Revises: 0009_add_customer_lifecycle
Create Date: 2026-05-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_add_automation_rules"
down_revision = "0009_add_customer_lifecycle"
branch_labels = None
depends_on = None

ACTION_TYPE_ENUM = postgresql.ENUM(
    "add_customer_tag", "create_customer_note", "emit_webhook_event", "create_notification_log",
    name="automation_action_type_enum",
    create_type=False,
)


def upgrade() -> None:
    ACTION_TYPE_ENUM.create(op.get_bind(), checkfirst=True)

    # Add allow_automation_rules to plans
    op.add_column("plans", sa.Column("allow_automation_rules", sa.Boolean(),
                                     nullable=True, server_default=sa.text("false")))

    op.create_table(
        "automation_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("trigger_event", sa.String(100), nullable=False),
        sa.Column("conditions", postgresql.JSONB(), nullable=True),
        sa.Column("action_type", ACTION_TYPE_ENUM, nullable=False),
        sa.Column("action_config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_automation_rules_tenant_id", "automation_rules", ["tenant_id"])
    op.create_index("ix_automation_rules_trigger_event", "automation_rules", ["trigger_event"])
    op.create_index("ix_automation_rules_action_type", "automation_rules", ["action_type"])
    op.create_index("ix_automation_rules_is_active", "automation_rules", ["is_active"])
    op.create_index(
        "ix_automation_rules_tenant_trigger_active",
        "automation_rules",
        ["tenant_id", "trigger_event", "is_active"],
    )


def downgrade() -> None:
    op.drop_table("automation_rules")
    op.drop_column("plans", "allow_automation_rules")
    ACTION_TYPE_ENUM.drop(op.get_bind(), checkfirst=True)
