"""add billing_mode to tenant_subscriptions

Revision ID: 0020_add_billing_mode
Revises: 0019_add_task_runs
Create Date: 2026-05-08

Adds the `billing_mode` column controlling how the billing cron treats this
subscription:
  - manual    (default): generate invoices but never auto-suspend
  - automatic         : full auto enforcement
  - free              : no invoice, cron never touches

Existing rows default to 'manual' — safest, preserves user control.
"""
from alembic import op
import sqlalchemy as sa


revision = "0020_add_billing_mode"
down_revision = "0019_add_task_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_subscriptions",
        sa.Column(
            "billing_mode", sa.String(20), nullable=False,
            server_default="manual",
        ),
    )
    op.create_check_constraint(
        "ck_tenant_subscriptions_billing_mode",
        "tenant_subscriptions",
        "billing_mode IN ('manual','automatic','free')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_tenant_subscriptions_billing_mode", "tenant_subscriptions",
    )
    op.drop_column("tenant_subscriptions", "billing_mode")
