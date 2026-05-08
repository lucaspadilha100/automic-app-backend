from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from app.models.owner_notification import (
    OwnerNotificationType, OwnerNotificationSeverity,
)


class OwnerNotificationResponse(BaseModel):
    id: uuid.UUID
    notification_type: OwnerNotificationType
    severity: OwnerNotificationSeverity
    title: str
    message: Optional[str]
    tenant_id: Optional[uuid.UUID]
    related_entity_type: Optional[str]
    related_entity_id: Optional[uuid.UUID]
    is_read: bool
    read_at: Optional[datetime]
    payload: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OwnerNotificationListResponse(BaseModel):
    items: List[OwnerNotificationResponse]
    total: int
    unread: int


class OwnerNotificationReadUpdate(BaseModel):
    is_read: bool = True
