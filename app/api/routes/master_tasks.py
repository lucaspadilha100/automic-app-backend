"""Master tasks routes — list TaskRun audit history."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import require_super_admin
from app.models.user import User
from app.models.task_run import TaskRunStatus
from app.schemas.task_run import TaskRunListResponse
from app.services.task_run_service import task_run_service

router = APIRouter(prefix="/master/tasks", tags=["Tasks - Master"])


@router.get("", response_model=TaskRunListResponse)
def list_task_runs(
    task_name: Optional[str] = Query(None),
    status: Optional[TaskRunStatus] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    items = task_run_service.list_runs(
        db, task_name=task_name, status=status, limit=limit, offset=offset,
    )
    total = task_run_service.count(db, task_name=task_name, status=status)
    return {"items": items, "total": total}
