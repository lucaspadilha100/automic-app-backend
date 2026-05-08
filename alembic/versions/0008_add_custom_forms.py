"""add custom forms

Revision ID: 0008_add_custom_forms
Revises: 0007_add_professional_commissions
Create Date: 2026-05-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_add_custom_forms"
down_revision = "0007_add_professional_commissions"
branch_labels = None
depends_on = None

FORM_TYPE_ENUM = postgresql.ENUM(
    "anamnesis", "pre_service", "post_service", "evaluation",
    name="form_type_enum",
    create_type=False,
)
FIELD_TYPE_ENUM = postgresql.ENUM(
    "text", "textarea", "number", "date", "boolean", "select", "multiselect",
    name="field_type_enum",
    create_type=False,
)


def upgrade() -> None:
    FORM_TYPE_ENUM.create(op.get_bind(), checkfirst=True)
    FIELD_TYPE_ENUM.create(op.get_bind(), checkfirst=True)

    # Add allow_custom_forms to plans if not present
    op.add_column("plans", sa.Column("allow_custom_forms", sa.Boolean(), nullable=True, server_default=sa.text("false")))

    op.create_table(
        "custom_forms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("form_type", FORM_TYPE_ENUM, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_custom_forms_tenant_id", "custom_forms", ["tenant_id"])
    op.create_index("ix_custom_forms_form_type", "custom_forms", ["form_type"])
    op.create_index("ix_custom_forms_is_active", "custom_forms", ["is_active"])
    op.create_index("ix_custom_forms_tenant_type_active", "custom_forms", ["tenant_id", "form_type", "is_active"])

    op.create_table(
        "custom_form_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("form_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("custom_forms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("field_type", FIELD_TYPE_ENUM, nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("options", postgresql.JSONB(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_custom_form_fields_tenant_id", "custom_form_fields", ["tenant_id"])
    op.create_index("ix_custom_form_fields_form_id", "custom_form_fields", ["form_id"])

    op.create_table(
        "custom_form_responses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("form_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("custom_forms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_account_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("customer_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tenant_customer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenant_customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("answers", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_custom_form_responses_tenant_id", "custom_form_responses", ["tenant_id"])
    op.create_index("ix_custom_form_responses_form_id", "custom_form_responses", ["form_id"])
    op.create_index("ix_custom_form_responses_customer_account_id", "custom_form_responses", ["customer_account_id"])
    op.create_index("ix_custom_form_responses_tenant_customer_id", "custom_form_responses", ["tenant_customer_id"])


def downgrade() -> None:
    op.drop_table("custom_form_responses")
    op.drop_table("custom_form_fields")
    op.drop_table("custom_forms")
    op.drop_column("plans", "allow_custom_forms")
    FORM_TYPE_ENUM.drop(op.get_bind(), checkfirst=True)
    FIELD_TYPE_ENUM.drop(op.get_bind(), checkfirst=True)
