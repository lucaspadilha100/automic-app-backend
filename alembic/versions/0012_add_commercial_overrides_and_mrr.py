"""add commercial overrides and mrr

Revision ID: 0012_add_commercial_overrides_and_mrr
Revises: 0011_add_whatsapp_settings
Create Date: 2026-05-07

Adds:
  - plans.allow_commissions
  - tenant_subscriptions.custom_price_monthly (numeric(10,2), nullable, >= 0)
  - tenant_subscriptions.custom_price_reason (text, nullable)
  - tenant_subscriptions.billing_notes (text, nullable)
  - tenant_subscriptions.contracted_at (timestamptz, nullable)

These columns power:
  - per-tenant feature override for "commissions" via plans.allow_commissions
  - per-tenant negotiated monthly price (effective MRR)
  - business notes captured during sales/renegotiation
"""
from alembic import op
import sqlalchemy as sa


revision = "0012_add_commercial_overrides_and_mrr"
down_revision = "0011_add_whatsapp_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── plans.allow_commissions ────────────────────────────────────────────────
    op.add_column(
        "plans",
        sa.Column(
            "allow_commissions", sa.Boolean(),
            nullable=True, server_default=sa.text("false"),
        ),
    )

    # ── tenant_subscriptions: custom price + billing metadata ──────────────────
    op.add_column(
        "tenant_subscriptions",
        sa.Column("custom_price_monthly", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "tenant_subscriptions",
        sa.Column("custom_price_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "tenant_subscriptions",
        sa.Column("billing_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "tenant_subscriptions",
        sa.Column("contracted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_check_constraint(
        "ck_tenant_subscriptions_custom_price_non_negative",
        "tenant_subscriptions",
        "custom_price_monthly IS NULL OR custom_price_monthly >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_tenant_subscriptions_custom_price_non_negative",
        "tenant_subscriptions",
        type_="check",
    )
    op.drop_column("tenant_subscriptions", "contracted_at")
    op.drop_column("tenant_subscriptions", "billing_notes")
    op.drop_column("tenant_subscriptions", "custom_price_reason")
    op.drop_column("tenant_subscriptions", "custom_price_monthly")

    op.drop_column("plans", "allow_commissions")
