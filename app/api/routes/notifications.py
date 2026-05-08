from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import uuid

from db.session import get_db
from app.core.dependencies import require_active_tenant, require_manager_or_above
from app.models.user import User
from app.models.tenant import Tenant
from app.services.notification_service import notification_service

router = APIRouter(prefix="/notifications", tags=["Notificações - Logs"])


@router.get("/logs")
def list_notification_logs(
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(50, le=200),
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    logs = notification_service.get_logs(
        db=db,
        tenant_id=tenant.id,
        event_type=event_type,
        status=status,
        skip=skip,
        limit=limit,
    )
    return [
        {
            "id": str(log.id),
            "channel": log.channel,
            "event_type": log.event_type,
            "status": log.status,
            "customer_account_id": str(log.customer_account_id) if log.customer_account_id else None,
            "appointment_id": str(log.appointment_id) if log.appointment_id else None,
            "error_message": log.error_message,
            "sent_at": log.sent_at.isoformat() if log.sent_at else None,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
