"""
TaskRun — audit trail of background task executions.

Every time a job runs (whether by the worker, by manual master endpoint, or
by external cron), a TaskRun row is recorded with status, duration, errors
and a JSON summary. The master inbox queries this for the 'Tasks' page.

Status flow:
    started -> success
    started -> failed  (on exception)

Idempotent helpers in TaskRunService take care of inserting + updating.
"""
import enum
from sqlalchemy import (
    Column, String, Text, DateTime, Integer, Index, Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base_model import UUIDPrimaryKey, TimestampMixin
from db.base import Base


class TaskRunStatus(str, enum.Enum):
    started = "started"
    success = "success"
    failed = "failed"


class TaskRunSource(str, enum.Enum):
    worker = "worker"            # automatic via Arq scheduler
    manual = "manual"            # via /master/jobs/* endpoint
    cron = "cron"                # via external scheduler (cron, k8s job, etc)


class TaskRun(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "task_runs"

    task_name = Column(String(100), nullable=False, index=True)
    source = Column(
        SAEnum(TaskRunSource, name="task_run_source", create_type=False),
        nullable=False, default=TaskRunSource.manual,
    )
    status = Column(
        SAEnum(TaskRunStatus, name="task_run_status", create_type=False),
        nullable=False, default=TaskRunStatus.started, index=True,
    )

    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # JSON summary of what the task did (counts, ids, etc)
    summary = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_task_runs_task_status", "task_name", "status"),
        Index("ix_task_runs_started_at", "started_at"),
    )
