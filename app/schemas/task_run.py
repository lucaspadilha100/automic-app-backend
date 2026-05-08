from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from app.models.task_run import TaskRunStatus, TaskRunSource


class TaskRunResponse(BaseModel):
    id: uuid.UUID
    task_name: str
    source: TaskRunSource
    status: TaskRunStatus
    started_at: datetime
    finished_at: Optional[datetime]
    duration_ms: Optional[int]
    summary: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TaskRunListResponse(BaseModel):
    items: List[TaskRunResponse]
    total: int
