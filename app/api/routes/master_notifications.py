"""Master inbox of operational notifications for the AUTOMIC owner."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import require_super_admin
from app.models.user import User
from app.schemas.owner_notification import (
    OwnerNotificationResponse,
    OwnerNotificationListResponse,
    OwnerNotificationReadUpdate,
)
from app.services.owner_notification_service import owner_notification_service

router = APIRouter(prefix="/master/notifications", tags=["Notificações - Master"])


@router.get("", response_model=OwnerNotificationListResponse)
def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    items = owner_notification_service.list(
        db, unread_only=unread_only, limit=limit, offset=offset,
    )
    return {
        "items": items,
        "total": owner_notification_service.count_total(db),
        "unread": owner_notification_service.count_unread(db),
    }


@router.get("/unread-count")
def unread_count(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return {"unread": owner_notification_service.count_unread(db)}


@router.patch("/{notification_id}/read", response_model=OwnerNotificationResponse)
def mark_read(
    notification_id: str,
    payload: OwnerNotificationReadUpdate,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    note = owner_notification_service.mark_read(
        db, uuid.UUID(notification_id), is_read=payload.is_read,
    )
    if not note:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Notificação não encontrada")
    return note


@router.post("/mark-all-read")
def mark_all_read(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    count = owner_notification_service.mark_all_read(db)
    return {"marked": count}
