"""add customer lifecycle

Revision ID: 0009_add_customer_lifecycle
Revises: 0008_add_custom_forms
Create Date: 2026-05-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_add_customer_lifecycle"
down_revision = "0008_add_custom_forms"
branch_labels = None
depends_on = None

LIFECYCLE_STATUS_ENUM = postgresql.ENUM(
    "new", "active", "recurring", "inactive", "at_risk", "vip",
    name="lifecycle_status_enum",
    create_type=False,
)


def upgrade() -> None:
    LIFECYCLE_STATUS_ENUM.create(op.get_bind(), checkfirst=True)

    # Add allow_customer_lifecycle to plans
    op.add_column("plans", sa.Column("allow_customer_lifecycle", sa.Boolean(),
                                     nullable=True, server_default=sa.text("false")))

    # Add lifecycle fields to tenant_customers
    op.add_column("tenant_customers", sa.Column(
        "lifecycle_status",
        LIFECYCLE_STATUS_ENUM,
        nullable=False,
        server_default="new",
    ))
    op.add_column("tenant_customers", sa.Column("last_appointment_at",
                  sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenant_customers", sa.Column("next_appointment_at",
                  sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenant_customers", sa.Column("total_spent",
                  sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("tenant_customers", sa.Column("appointments_count",
                  sa.Integer(), nullable=False, server_default="0"))
    op.add_column("tenant_customers", sa.Column("no_show_count",
                  sa.Integer(), nullable=False, server_default="0"))

    # Constraints
    op.create_check_constraint(
        "ck_tenant_customers_total_spent_non_negative",
        "tenant_customers",
        "total_spent >= 0",
    )
    op.create_check_constraint(
        "ck_tenant_customers_appointments_count_non_negative",
        "tenant_customers",
        "appointments_count >= 0",
    )
    op.create_check_constraint(
        "ck_tenant_customers_no_show_count_non_negative",
        "tenant_customers",
        "no_show_count >= 0",
    )

    # Indices on tenant_customers lifecycle fields
    op.create_index("ix_tenant_customers_lifecycle_status", "tenant_customers",
                    ["tenant_id", "lifecycle_status"])
    op.create_index("ix_tenant_customers_last_appointment_at", "tenant_customers",
                    ["tenant_id", "last_appointment_at"])
    op.create_index("ix_tenant_customers_next_appointment_at", "tenant_customers",
                    ["tenant_id", "next_appointment_at"])
    op.create_index("ix_tenant_customers_total_spent", "tenant_customers",
                    ["tenant_id", "total_spent"])
    op.create_index("ix_tenant_customers_no_show_count", "tenant_customers",
                    ["tenant_id", "no_show_count"])

    # tenant_lifecycle_settings table
    op.create_table(
        "tenant_lifecycle_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("inactive_after_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("at_risk_after_days", sa.Integer(), nullable=False, server_default="45"),
        sa.Column("recurring_min_appointments", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("vip_min_appointments", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("vip_min_total_spent", sa.Numeric(12, 2), nullable=False, server_default="1000"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_tenant_lifecycle_settings_tenant_id", "tenant_lifecycle_settings", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("tenant_lifecycle_settings")
    op.drop_index("ix_tenant_customers_no_show_count", "tenant_customers")
    op.drop_index("ix_tenant_customers_total_spent", "tenant_customers")
    op.drop_index("ix_tenant_customers_next_appointment_at", "tenant_customers")
    op.drop_index("ix_tenant_customers_last_appointment_at", "tenant_customers")
    op.drop_index("ix_tenant_customers_lifecycle_status", "tenant_customers")
    op.drop_constraint("ck_tenant_customers_no_show_count_non_negative", "tenant_customers")
    op.drop_constraint("ck_tenant_customers_appointments_count_non_negative", "tenant_customers")
    op.drop_constraint("ck_tenant_customers_total_spent_non_negative", "tenant_customers")
    op.drop_column("tenant_customers", "no_show_count")
    op.drop_column("tenant_customers", "appointments_count")
    op.drop_column("tenant_customers", "total_spent")
    op.drop_column("tenant_customers", "next_appointment_at")
    op.drop_column("tenant_customers", "last_appointment_at")
    op.drop_column("tenant_customers", "lifecycle_status")
    op.drop_column("plans", "allow_customer_lifecycle")
    LIFECYCLE_STATUS_ENUM.drop(op.get_bind(), checkfirst=True)
