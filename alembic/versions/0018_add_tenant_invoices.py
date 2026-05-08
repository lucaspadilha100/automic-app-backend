"""add tenant invoices

Revision ID: 0018_add_tenant_invoices
Revises: 0017_add_onboarding_columns
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0018_add_tenant_invoices"
down_revision = "0017_add_onboarding_columns"
branch_labels = None
depends_on = None


INVOICE_STATUS_ENUM = postgresql.ENUM(
    "pending", "paid", "overdue", "cancelled",
    name="invoice_status",
    create_type=False,
)


def upgrade() -> None:
    INVOICE_STATUS_ENUM.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tenant_invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenant_subscriptions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("plan_name_snapshot", sa.String(100), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="BRL"),
        sa.Column("status", INVOICE_STATUS_ENUM, nullable=False, server_default="pending"),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("payment_provider", sa.String(50), nullable=True),
        sa.Column("payment_reference", sa.String(255), nullable=True),
        sa.Column("payment_qr_code", sa.Text(), nullable=True),
        sa.Column("payment_link", sa.String(500), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("provider_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "period_start", "period_end",
                            name="uq_tenant_invoices_tenant_period"),
        sa.CheckConstraint("amount >= 0", name="ck_tenant_invoices_amount_non_negative"),
    )
    op.create_index("ix_tenant_invoices_tenant_id", "tenant_invoices", ["tenant_id"])
    op.create_index("ix_tenant_invoices_subscription_id", "tenant_invoices", ["subscription_id"])
    op.create_index("ix_tenant_invoices_status", "tenant_invoices", ["status"])
    op.create_index("ix_tenant_invoices_status_due_date", "tenant_invoices",
                    ["status", "due_date"])


def downgrade() -> None:
    op.drop_table("tenant_invoices")
    INVOICE_STATUS_ENUM.drop(op.get_bind(), checkfirst=True)
