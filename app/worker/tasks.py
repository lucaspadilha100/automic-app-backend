"""
Arq worker settings + tasks.

Run the worker with:
    arq app.worker.tasks.WorkerSettings

Requires Redis at REDIS_URL (default: redis://localhost:6379).

Each task creates a fresh DB Session, runs the work inside a TaskRun
audit record, and commits/rolls back independently. The worker is
optional — if you don't run it, the same jobs can be triggered manually
via /master/jobs/* endpoints. They share the same service code, so
behavior is identical.
"""
from __future__ import annotations
import logging
import os
from typing import Optional

from app.core.logging_config import configure_logging
from app.core.middleware import install_log_filter
from app.models.task_run import TaskRunSource

logger = logging.getLogger("automic.worker")


def _new_session():
    """Create a standalone DB session (worker doesn't use FastAPI DI)."""
    from db.session import SessionLocal
    return SessionLocal()


# ── Tasks ─────────────────────────────────────────────────────────────────────

async def expire_trials_task(ctx: dict) -> dict:
    """Periodic: suspend tenants whose trial is over."""
    from app.services.tenant_ops_service import tenant_ops_service
    from app.services.task_run_service import task_run_service

    db = _new_session()
    try:
        with task_run_service.record(db, "expire_trials", TaskRunSource.worker) as run_ctx:
            result = tenant_ops_service.expire_trials(db)
            run_ctx.set_summary(result)
            logger.info(
                "expire_trials done",
                extra={"task_name": "expire_trials", "task_run_id": str(run_ctx.run.id)},
            )
            return result
    finally:
        db.close()


async def mark_overdue_invoices_task(ctx: dict) -> dict:
    from app.services.invoice_service import invoice_service
    from app.services.task_run_service import task_run_service

    db = _new_session()
    try:
        with task_run_service.record(db, "mark_overdue_invoices", TaskRunSource.worker) as run_ctx:
            result = invoice_service.mark_overdue(db)
            run_ctx.set_summary(result)
            return result
    finally:
        db.close()


async def enforce_billing_task(ctx: dict) -> dict:
    from app.services.invoice_service import invoice_service
    from app.services.task_run_service import task_run_service

    db = _new_session()
    try:
        with task_run_service.record(db, "enforce_billing", TaskRunSource.worker) as run_ctx:
            result = invoice_service.enforce_billing(db)
            run_ctx.set_summary(result)
            return result
    finally:
        db.close()


async def generate_monthly_invoices_task(ctx: dict) -> dict:
    from app.services.invoice_service import invoice_service
    from app.services.task_run_service import task_run_service

    db = _new_session()
    try:
        with task_run_service.record(db, "generate_monthly_invoices", TaskRunSource.worker) as run_ctx:
            result = invoice_service.generate_monthly_invoices(db)
            run_ctx.set_summary(result)
            return result
    finally:
        db.close()


async def send_24h_reminders_task(ctx: dict) -> dict:
    from app.services.reminder_service import reminder_service
    from app.services.task_run_service import task_run_service

    db = _new_session()
    try:
        with task_run_service.record(db, "send_24h_reminders", TaskRunSource.worker) as run_ctx:
            result = reminder_service.send_24h_reminders(db)
            run_ctx.set_summary(result)
            return result
    finally:
        db.close()


async def startup(ctx):
    configure_logging()
    install_log_filter()
    logger.info("AUTOMIC worker starting up")


async def shutdown(ctx):
    logger.info("AUTOMIC worker shutting down")


# ── Worker settings (consumed by `arq app.worker.tasks.WorkerSettings`) ───────

def _redis_settings():
    from arq.connections import RedisSettings
    url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    return RedisSettings.from_dsn(url)


def _cron_jobs():
    """
    Cron schedule. Times are UTC by default.

    - send_24h_reminders           — every hour (sweeps appointments 23-25h ahead)
    - expire_trials                — every day at 03:00 UTC (00:00 BRT)
    - mark_overdue_invoices        — every day at 03:10 UTC
    - enforce_billing              — every day at 03:20 UTC
    - generate_monthly_invoices    — first of every month at 03:30 UTC
    """
    from arq.cron import cron
    return [
        cron(send_24h_reminders_task, minute={0}),  # hourly at :00
        cron(expire_trials_task, hour={3}, minute={0}),
        cron(mark_overdue_invoices_task, hour={3}, minute={10}),
        cron(enforce_billing_task, hour={3}, minute={20}),
        cron(generate_monthly_invoices_task, day={1}, hour={3}, minute={30}),
    ]


class WorkerSettings:
    """Picked up by Arq's CLI."""
    functions = [
        expire_trials_task, mark_overdue_invoices_task,
        enforce_billing_task, generate_monthly_invoices_task,
        send_24h_reminders_task,
    ]
    on_startup = startup
    on_shutdown = shutdown

    @staticmethod
    def get_cron_jobs():
        return _cron_jobs()

    # arq looks for `cron_jobs` and `redis_settings` as class attributes;
    # we wire them via descriptors so import doesn't require redis at module load.

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)


# Defer evaluation of cron_jobs/redis_settings until arq actually reads them
def _attach_lazy(cls):
    cls.cron_jobs = property(lambda self: _cron_jobs())  # not used — arq reads class attr
    return cls


# Arq reads these as class attributes:
WorkerSettings.cron_jobs = _cron_jobs()
WorkerSettings.redis_settings = _redis_settings()
