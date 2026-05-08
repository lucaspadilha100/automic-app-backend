"""add schedule_exceptions + reschedule chain

Revision ID: 0021_add_schedule_exceptions
Revises: 0020_add_billing_mode
Create Date: 2026-05-08

Adds:
  1. schedule_exceptions table — blocks time windows from being booked
     (holidays, professional leave, clinic closures).
  2. appointments.rescheduled_from_id and appointments.rescheduled_to_id —
     self-referencing FKs that track the chain when an appointment is
     rescheduled, so we can answer 'this appointment came from which one?'
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0021_add_schedule_exceptions"
down_revision = "0020_add_billing_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── schedule_exceptions ──────────────────────────────────────────────────
    op.create_table(
        "schedule_exceptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "professional_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("professionals.id", ondelete="CASCADE"), nullable=True,
        ),
        sa.Column(
            "unit_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("units.id", ondelete="CASCADE"), nullable=True,
        ),
        sa.Column("start_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exception_type", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "exception_type IN ('holiday','leave','closure')",
            name="ck_schedule_exceptions_type",
        ),
        sa.CheckConstraint(
            "end_datetime > start_datetime",
            name="ck_schedule_exceptions_range",
        ),
    )
    op.create_index("ix_schedule_exceptions_tenant_id", "schedule_exceptions", ["tenant_id"])
    op.create_index("ix_schedule_exceptions_professional_id", "schedule_exceptions", ["professional_id"])
    op.create_index("ix_schedule_exceptions_unit_id", "schedule_exceptions", ["unit_id"])
    op.create_index("ix_schedule_exceptions_start_datetime", "schedule_exceptions", ["start_datetime"])
    op.create_index("ix_schedule_exceptions_end_datetime", "schedule_exceptions", ["end_datetime"])
    op.create_index(
        "ix_schedule_exceptions_window",
        "schedule_exceptions", ["tenant_id", "start_datetime", "end_datetime"],
    )
    op.create_index(
        "ix_schedule_exceptions_prof_window",
        "schedule_exceptions", ["professional_id", "start_datetime", "end_datetime"],
    )

    # ── reschedule chain on appointments ─────────────────────────────────────
    op.add_column(
        "appointments",
        sa.Column(
            "rescheduled_from_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("appointments.id"), nullable=True,
        ),
    )
    op.add_column(
        "appointments",
        sa.Column(
            "rescheduled_to_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("appointments.id"), nullable=True,
        ),
    )
    op.create_index(
        "ix_appointments_rescheduled_from_id", "appointments", ["rescheduled_from_id"],
    )
    op.create_index(
        "ix_appointments_rescheduled_to_id", "appointments", ["rescheduled_to_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_appointments_rescheduled_to_id", table_name="appointments")
    op.drop_index("ix_appointments_rescheduled_from_id", table_name="appointments")
    op.drop_column("appointments", "rescheduled_to_id")
    op.drop_column("appointments", "rescheduled_from_id")

    op.drop_table("schedule_exceptions")
