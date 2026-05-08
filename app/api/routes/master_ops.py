"""
Master operations routes — trial expiration job and tenant health dashboard.

These complement /master/tenants by providing operational views and actions
that the AUTOMIC owner uses day-to-day.
"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import require_super_admin
from app.models.user import User
from app.models.task_run import TaskRunSource
from app.services.tenant_ops_service import tenant_ops_service
from app.services.task_run_service import task_run_service
from app.services.reminder_service import reminder_service

router = APIRouter(prefix="/master", tags=["Operações - Master"])


@router.get("/health/tenants")
def tenants_health(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Snapshot de saúde de todos os tenants (com churn risk)."""
    return tenant_ops_service.compute_tenant_health(db)


@router.post("/jobs/run-trial-expiration")
def run_trial_expiration(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Roda o job de expiração de trials manualmente.
    Idempotente — pode ser chamado várias vezes seguidas sem duplicar efeito.
    Cada execução é registrada em TaskRun.
    """
    with task_run_service.record(db, "expire_trials", TaskRunSource.manual) as ctx:
        result = tenant_ops_service.expire_trials(db)
        ctx.set_summary(result)
        return result


@router.post("/jobs/send-24h-reminders")
def run_24h_reminders(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Envia lembretes de agendamento 24h antes (idempotente).
    Designed to run hourly. Skips appointments that already have a sent log.
    """
    with task_run_service.record(db, "send_24h_reminders", TaskRunSource.manual) as ctx:
        result = reminder_service.send_24h_reminders(db)
        ctx.set_summary(result)
        return result
