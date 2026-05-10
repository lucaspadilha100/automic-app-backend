"""Add registered_by_user_id to payments

Revision ID: 0024_add_payment_registered_by
Revises: 0023_add_products_supplies
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0024_add_payment_registered_by'
down_revision = '0023_add_products_supplies'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('payments', sa.Column(
        'registered_by_user_id',
        UUID(as_uuid=True),
        sa.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
    ))


def downgrade():
    op.drop_column('payments', 'registered_by_user_id')
