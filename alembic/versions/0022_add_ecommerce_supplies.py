"""add ecommerce and product_usage tables

Revision ID: 0022_add_ecommerce_supplies
Revises: 0021_add_schedule_exceptions
Create Date: 2026-05-10

Adds:
  1. product_categories — categories for products sold to customers
  2. products — items for sale (ecommerce feature)
  3. product_orders — customer product orders
  4. product_order_items — line items for product orders
  5. supplies — internal supplies used during appointments (product_usage feature)
  6. appointment_supply_usage — records of supply consumption per appointment
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0022_add_ecommerce_supplies"
down_revision = "0021_add_schedule_exceptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── product_categories ───────────────────────────────────────────────────
    op.create_table(
        "product_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "name", name="uq_product_categories_tenant_name"),
    )
    op.create_index("ix_product_categories_tenant_id", "product_categories", ["tenant_id"])

    # ── products ─────────────────────────────────────────────────────────────
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "category_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_categories.id"), nullable=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("track_stock", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("stock_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("low_stock_threshold", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("price >= 0", name="ck_products_price_non_negative"),
        sa.CheckConstraint("stock_quantity >= 0", name="ck_products_stock_non_negative"),
    )
    op.create_index("ix_products_tenant_id", "products", ["tenant_id"])
    op.create_index("ix_products_category_id", "products", ["category_id"])

    # ── product_orders ───────────────────────────────────────────────────────
    op.create_table(
        "product_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "customer_account_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_accounts.id"), nullable=True,
        ),
        sa.Column("customer_name", sa.String(200), nullable=True),
        sa.Column("customer_phone", sa.String(30), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("payment_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("payment_method", sa.String(30), nullable=True),
        sa.Column("total", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_product_orders_tenant_id", "product_orders", ["tenant_id"])
    op.create_index("ix_product_orders_customer_account_id", "product_orders", ["customer_account_id"])

    # ── product_order_items ──────────────────────────────────────────────────
    op.create_table(
        "product_order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "order_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_orders.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "product_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id"), nullable=False,
        ),
        sa.Column("product_name_snapshot", sa.String(200), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
    )
    op.create_index("ix_product_order_items_order_id", "product_order_items", ["order_id"])

    # ── supplies ─────────────────────────────────────────────────────────────
    op.create_table(
        "supplies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(20), nullable=False, server_default="un"),
        sa.Column("cost_price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("track_stock", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("stock_quantity", sa.Numeric(10, 3), nullable=False, server_default="0"),
        sa.Column("low_stock_threshold", sa.Numeric(10, 3), nullable=False, server_default="5"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_supplies_tenant_id", "supplies", ["tenant_id"])

    # ── appointment_supply_usage ──────────────────────────────────────────────
    op.create_table(
        "appointment_supply_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "appointment_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "supply_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("supplies.id"), nullable=False,
        ),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("quantity_used", sa.Numeric(10, 3), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_appointment_supply_usage_appointment_id", "appointment_supply_usage", ["appointment_id"])
    op.create_index("ix_appointment_supply_usage_tenant_id", "appointment_supply_usage", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("appointment_supply_usage")
    op.drop_table("supplies")
    op.drop_table("product_order_items")
    op.drop_table("product_orders")
    op.drop_table("products")
    op.drop_table("product_categories")
