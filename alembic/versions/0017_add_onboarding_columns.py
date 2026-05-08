"""add onboarding columns to tenant_subscriptions

Revision ID: 0017_add_onboarding_columns
Revises: 0016_add_platform_documents
Create Date: 2026-05-08

Adds the three columns used by the self-service onboarding flow:
  - accepted_terms_at      — when the owner accepted ToS at signup
  - accepted_terms_version — which ToS version was accepted (audit trail)
  - signup_source          — 'self_service' | 'manual_master' | etc.

All three are nullable so existing subscriptions (created via /master) remain valid.
"""
from alembic import op
import sqlalchemy as sa


revision = "0017_add_onboarding_columns"
down_revision = "0016_add_platform_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_subscriptions",
        sa.Column("accepted_terms_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenant_subscriptions",
        sa.Column("accepted_terms_version", sa.String(20), nullable=True),
    )
    op.add_column(
        "tenant_subscriptions",
        sa.Column("signup_source", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenant_subscriptions", "signup_source")
    op.drop_column("tenant_subscriptions", "accepted_terms_version")
    op.drop_column("tenant_subscriptions", "accepted_terms_at")
