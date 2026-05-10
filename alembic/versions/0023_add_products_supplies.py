"""add products and supplies tables

Revision ID: 0023_add_products_supplies
Revises: 0022_add_page_sections
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0023_add_products_supplies'
down_revision = '0022_add_page_sections'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'product_categories',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(150), nullable=False),
        sa.Column('sort_order', sa.Integer, nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'products',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('category_id', UUID(as_uuid=True), sa.ForeignKey('product_categories.id', ondelete='SET NULL'), nullable=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('price', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('image_url', sa.String(500), nullable=True),
        sa.Column('track_stock', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('stock_quantity', sa.Integer, nullable=True),
        sa.Column('low_stock_threshold', sa.Integer, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'product_orders',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('customer_account_id', UUID(as_uuid=True), sa.ForeignKey('customer_accounts.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('customer_name', sa.String(200), nullable=False),
        sa.Column('customer_phone', sa.String(30), nullable=True),
        sa.Column('items', JSONB, nullable=False, server_default='[]'),
        sa.Column('total', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('payment_status', sa.String(20), nullable=False, server_default='unpaid'),
        sa.Column('payment_method', sa.String(50), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'supplies',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('unit', sa.String(20), nullable=False, server_default='un'),
        sa.Column('cost_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('track_stock', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('stock_quantity', sa.Numeric(10, 3), nullable=True),
        sa.Column('low_stock_threshold', sa.Numeric(10, 3), nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'appointment_supply_usages',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('appointment_id', UUID(as_uuid=True), sa.ForeignKey('appointments.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('supply_id', UUID(as_uuid=True), sa.ForeignKey('supplies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('quantity_used', sa.Numeric(10, 3), nullable=False),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('appointment_supply_usages')
    op.drop_table('supplies')
    op.drop_table('product_orders')
    op.drop_table('products')
    op.drop_table('product_categories')
