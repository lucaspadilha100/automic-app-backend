"""add page_sections to tenant_settings

Revision ID: 0022_add_page_sections
Revises: 0021_add_schedule_exceptions
Create Date: 2026-05-10

Adds a JSONB column `page_sections` to `tenant_settings` that stores per-section
customization (title, subtitle, background color/image, visibility) for the
public booking page and customer portal.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0022_add_page_sections"
down_revision = "0021_add_schedule_exceptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_settings",
        sa.Column("page_sections", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenant_settings", "page_sections")
