"""add professional commissions

Revision ID: 0007_add_professional_commissions
Revises: 0006_add_procedure_photos
Create Date: 2026-05-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_add_professional_commissions"
down_revision = "0006_add_procedure_photos"
branch_labels = None
depends_on = None

COMMISSION_TYPE_ENUM = postgresql.ENUM(
    "percentage", "fixed", "none",
    name="commission_type_enum",
    create_type=False,
)
COMMISSION_STATUS_ENUM = postgresql.ENUM(
    "pending", "paid", "cancelled",
    name="commission_status_enum",
    create_type=False,
)


def upgrade() -> None:
    COMMISSION_TYPE_ENUM.create(op.get_bind(), checkfirst=True)
    COMMISSION_STATUS_ENUM.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "professional_commission_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("commission_type", COMMISSION_TYPE_ENUM, nullable=False),
        sa.Column("commission_value", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("commission_value >= 0", name="ck_commission_settings_value_non_negative"),
    )
    op.create_index("ix_commission_settings_tenant_id", "professional_commission_settings", ["tenant_id"])
    op.create_index("ix_commission_settings_professional_id", "professional_commission_settings", ["professional_id"])
    op.create_index("ix_commission_settings_is_active", "professional_commission_settings", ["is_active"])
    op.create_index(
        "ix_commission_settings_tenant_professional",
        "professional_commission_settings",
        ["tenant_id", "professional_id"],
    )

    op.create_table(
        "commission_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("professional_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("base_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("commission_type", COMMISSION_TYPE_ENUM, nullable=False),
        sa.Column("commission_value", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("commission_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("status", COMMISSION_STATUS_ENUM, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("base_amount >= 0", name="ck_commission_records_base_non_negative"),
        sa.CheckConstraint("commission_value >= 0", name="ck_commission_records_value_non_negative"),
        sa.CheckConstraint("commission_amount >= 0", name="ck_commission_records_amount_non_negative"),
    )
    op.create_index("ix_commission_records_tenant_id", "commission_records", ["tenant_id"])
    op.create_index("ix_commission_records_appointment_id", "commission_records", ["appointment_id"])
    op.create_index("ix_commission_records_professional_id", "commission_records", ["professional_id"])
    op.create_index("ix_commission_records_status", "commission_records", ["status"])
    op.create_index(
        "ix_commission_records_appointment_professional",
        "commission_records",
        ["appointment_id", "professional_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("commission_records")
    op.drop_table("professional_commission_settings")
    COMMISSION_TYPE_ENUM.drop(op.get_bind(), checkfirst=True)
    COMMISSION_STATUS_ENUM.drop(op.get_bind(), checkfirst=True)
