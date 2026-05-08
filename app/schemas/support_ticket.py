from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, List
from datetime import datetime
import uuid

from app.models.support_ticket import (
    SupportTicketStatus, SupportTicketCategory, SupportTicketPriority,
)


# ── Messages ──────────────────────────────────────────────────────────────────

class SupportTicketMessageCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=10000)


class SupportTicketMessageResponse(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    author_user_id: Optional[uuid.UUID]
    author_side: str
    body: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── Tickets ───────────────────────────────────────────────────────────────────

class SupportTicketCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1, max_length=10000)
    category: SupportTicketCategory = SupportTicketCategory.question
    priority: SupportTicketPriority = SupportTicketPriority.normal


class SupportTicketResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_by_user_id: Optional[uuid.UUID]
    assigned_to_user_id: Optional[uuid.UUID]
    subject: str
    category: SupportTicketCategory
    priority: SupportTicketPriority
    status: SupportTicketStatus
    last_message_at: Optional[datetime]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SupportTicketWithMessagesResponse(SupportTicketResponse):
    messages: List[SupportTicketMessageResponse] = []


class SupportTicketStatusUpdate(BaseModel):
    status: SupportTicketStatus


class SupportTicketAssignUpdate(BaseModel):
    """Master atribui um super_admin (ou desatribui passando None)."""
    assigned_to_user_id: Optional[uuid.UUID] = None


class SupportTicketPriorityUpdate(BaseModel):
    priority: SupportTicketPriority
