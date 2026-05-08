"""add terms and acceptances

Revision ID: 0005_add_terms_and_acceptances
Revises: 0004_final_prompt_closure
Create Date: 2026-05-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_add_terms_and_acceptances"
down_revision = "0004_final_prompt_closure"
branch_labels = None
depends_on = None

TERM_TYPE_ENUM = postgresql.ENUM(
    "general",
    "procedure",
    "image_authorization",
    "privacy_policy",
    "post_procedure",
    name="term_type_enum",
    create_type=False,
)


def upgrade() -> None:
    TERM_TYPE_ENUM.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tenant_terms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("term_type", TERM_TYPE_ENUM, nullable=False),
        sa.Column("version", sa.String(50), nullable=False, server_default="1.0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_tenant_terms_tenant_id", "tenant_terms", ["tenant_id"])
    op.create_index("ix_tenant_terms_term_type", "tenant_terms", ["term_type"])
    op.create_index("ix_tenant_terms_is_active", "tenant_terms", ["is_active"])
    op.create_index("ix_tenant_terms_tenant_type_active", "tenant_terms", ["tenant_id", "term_type", "is_active"])

    op.create_table(
        "customer_term_acceptances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customer_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant_customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("term_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenant_terms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_customer_term_acceptances_tenant_id", "customer_term_acceptances", ["tenant_id"])
    op.create_index("ix_customer_term_acceptances_customer_account_id", "customer_term_acceptances", ["customer_account_id"])
    op.create_index("ix_customer_term_acceptances_term_id", "customer_term_acceptances", ["term_id"])


def downgrade() -> None:
    op.drop_table("customer_term_acceptances")
    op.drop_table("tenant_terms")
    TERM_TYPE_ENUM.drop(op.get_bind(), checkfirst=True)
