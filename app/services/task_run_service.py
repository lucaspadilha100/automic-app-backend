"""
Service for recording background task executions.

Provides a context manager `record(task_name, source)` that wraps any
callable, capturing status (success/failed), duration, summary and
error message. Always commits even on failure so the audit trail
survives the exception.
"""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable
import logging
import time
import uuid

from sqlalchemy.orm import Session

from app.models.task_run import TaskRun, TaskRunStatus, TaskRunSource

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskRunService:
    def list_runs(
        self,
        db: Session,
        task_name: Optional[str] = None,
        status: Optional[TaskRunStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[TaskRun]:
        return self._build_query(db, task_name, status).order_by(
            TaskRun.started_at.desc()
        ).offset(offset).limit(limit).all()

    def count(
        self,
        db: Session,
        task_name: Optional[str] = None,
        status: Optional[TaskRunStatus] = None,
    ) -> int:
        return self._build_query(db, task_name, status).count()

    def _build_query(
        self,
        db: Session,
        task_name: Optional[str],
        status: Optional[TaskRunStatus],
    ):
        q = db.query(TaskRun)
        if task_name:
            q = q.filter(TaskRun.task_name == task_name)
        if status:
            q = q.filter(TaskRun.status == status)
        return q

    def start(
        self,
        db: Session,
        task_name: str,
        source: TaskRunSource = TaskRunSource.manual,
    ) -> TaskRun:
        run = TaskRun(
            task_name=task_name,
            source=source,
            status=TaskRunStatus.started,
            started_at=_utcnow(),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    def finish_success(
        self, db: Session, run: TaskRun, summary: Optional[Dict[str, Any]] = None,
    ) -> TaskRun:
        run.status = TaskRunStatus.success
        run.finished_at = _utcnow()
        run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
        run.summary = summary
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    def finish_failed(
        self, db: Session, run: TaskRun, error: Exception,
        summary: Optional[Dict[str, Any]] = None,
    ) -> TaskRun:
        run.status = TaskRunStatus.failed
        run.finished_at = _utcnow()
        run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
        run.error_message = str(error)[:2000]
        run.summary = summary
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    @contextmanager
    def record(
        self,
        db: Session,
        task_name: str,
        source: TaskRunSource = TaskRunSource.manual,
    ):
        """
        Context manager that wraps task execution. Use as:

            with task_run_service.record(db, "expire_trials", TaskRunSource.manual) as ctx:
                summary = service.expire_trials(db)
                ctx.set_summary(summary)
        """
        run = self.start(db, task_name, source)
        ctx = _TaskRunContext(run)
        try:
            yield ctx
        except Exception as e:
            self.finish_failed(db, run, e, summary=ctx.summary)
            raise
        else:
            self.finish_success(db, run, summary=ctx.summary)


class _TaskRunContext:
    def __init__(self, run: TaskRun):
        self.run = run
        self.summary: Optional[Dict[str, Any]] = None

    def set_summary(self, summary: Optional[Dict[str, Any]]) -> None:
        # Coerce datetime/UUID/date to JSON-friendly types for storage in JSONB
        if summary is None:
            self.summary = None
            return
        from datetime import date
        clean = {}
        for k, v in summary.items():
            if isinstance(v, datetime):
                clean[k] = v.isoformat()
            elif isinstance(v, date):
                clean[k] = v.isoformat()
            elif isinstance(v, uuid.UUID):
                clean[k] = str(v)
            elif isinstance(v, list):
                clean[k] = [
                    str(item) if isinstance(item, uuid.UUID)
                    else item.isoformat() if isinstance(item, (datetime, date))
                    else item
                    for item in v
                ]
            else:
                clean[k] = v
        self.summary = clean


task_run_service = TaskRunService()
