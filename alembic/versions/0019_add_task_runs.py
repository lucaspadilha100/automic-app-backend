"""add task runs

Revision ID: 0019_add_task_runs
Revises: 0018_add_tenant_invoices
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0019_add_task_runs"
down_revision = "0018_add_tenant_invoices"
branch_labels = None
depends_on = None


TASK_RUN_SOURCE_ENUM = postgresql.ENUM(
    "worker", "manual", "cron",
    name="task_run_source",
    create_type=False,
)
TASK_RUN_STATUS_ENUM = postgresql.ENUM(
    "started", "success", "failed",
    name="task_run_status",
    create_type=False,
)


def upgrade() -> None:
    TASK_RUN_SOURCE_ENUM.create(op.get_bind(), checkfirst=True)
    TASK_RUN_STATUS_ENUM.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "task_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("task_name", sa.String(100), nullable=False),
        sa.Column("source", TASK_RUN_SOURCE_ENUM, nullable=False, server_default="manual"),
        sa.Column("status", TASK_RUN_STATUS_ENUM, nullable=False, server_default="started"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_task_runs_task_name", "task_runs", ["task_name"])
    op.create_index("ix_task_runs_status", "task_runs", ["status"])
    op.create_index("ix_task_runs_task_status", "task_runs", ["task_name", "status"])
    op.create_index("ix_task_runs_started_at", "task_runs", ["started_at"])


def downgrade() -> None:
    op.drop_table("task_runs")
    TASK_RUN_STATUS_ENUM.drop(op.get_bind(), checkfirst=True)
    TASK_RUN_SOURCE_ENUM.drop(op.get_bind(), checkfirst=True)
