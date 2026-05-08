"""
Support routes for the master/AUTOMIC side. Super admin can list and reply
to tickets across all tenants, and change priority/status/assignment.
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import require_super_admin
from app.models.user import User
from app.models.support_ticket import (
    SupportTicketStatus, SupportTicketPriority,
)
from app.schemas.support_ticket import (
    SupportTicketResponse, SupportTicketWithMessagesResponse,
    SupportTicketMessageResponse, SupportTicketMessageCreate,
    SupportTicketStatusUpdate, SupportTicketPriorityUpdate, SupportTicketAssignUpdate,
)
from app.services.support_ticket_service import support_ticket_service

router = APIRouter(prefix="/master/support/tickets", tags=["Suporte - Master"])


@router.get("", response_model=List[SupportTicketResponse])
def list_all_tickets(
    status: Optional[SupportTicketStatus] = Query(None),
    tenant_id: Optional[str] = Query(None),
    priority: Optional[SupportTicketPriority] = Query(None),
    assigned_to_user_id: Optional[str] = Query(None),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return support_ticket_service.list_all_tickets(
        db,
        status=status,
        tenant_id=uuid.UUID(tenant_id) if tenant_id else None,
        priority=priority,
        assigned_to=uuid.UUID(assigned_to_user_id) if assigned_to_user_id else None,
    )


@router.get("/{ticket_id}", response_model=SupportTicketWithMessagesResponse)
def get_ticket(
    ticket_id: str,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    ticket = support_ticket_service.get_ticket(db, uuid.UUID(ticket_id))
    msgs = support_ticket_service.list_messages(db, ticket.id)
    return _with_messages(ticket, msgs)


@router.post("/{ticket_id}/messages", response_model=SupportTicketMessageResponse, status_code=201)
def reply_ticket(
    ticket_id: str,
    payload: SupportTicketMessageCreate,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    ticket = support_ticket_service.get_ticket(db, uuid.UUID(ticket_id))
    return support_ticket_service.add_message(
        db=db, ticket=ticket,
        author_user_id=current_user.id,
        author_side="automic",
        body=payload.body,
    )


@router.patch("/{ticket_id}/status", response_model=SupportTicketResponse)
def set_status(
    ticket_id: str,
    payload: SupportTicketStatusUpdate,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    ticket = support_ticket_service.get_ticket(db, uuid.UUID(ticket_id))
    return support_ticket_service.set_status(db, ticket, payload.status)


@router.patch("/{ticket_id}/priority", response_model=SupportTicketResponse)
def set_priority(
    ticket_id: str,
    payload: SupportTicketPriorityUpdate,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    ticket = support_ticket_service.get_ticket(db, uuid.UUID(ticket_id))
    return support_ticket_service.set_priority(db, ticket, payload.priority)


@router.patch("/{ticket_id}/assign", response_model=SupportTicketResponse)
def assign(
    ticket_id: str,
    payload: SupportTicketAssignUpdate,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    ticket = support_ticket_service.get_ticket(db, uuid.UUID(ticket_id))
    return support_ticket_service.assign(db, ticket, payload.assigned_to_user_id)


def _with_messages(ticket, msgs):
    return SupportTicketWithMessagesResponse.model_validate({
        "id": ticket.id, "tenant_id": ticket.tenant_id,
        "created_by_user_id": ticket.created_by_user_id,
        "assigned_to_user_id": ticket.assigned_to_user_id,
        "subject": ticket.subject, "category": ticket.category,
        "priority": ticket.priority, "status": ticket.status,
        "last_message_at": ticket.last_message_at,
        "resolved_at": ticket.resolved_at,
        "created_at": ticket.created_at, "updated_at": ticket.updated_at,
        "messages": [
            {
                "id": m.id, "ticket_id": m.ticket_id, "author_user_id": m.author_user_id,
                "author_side": m.author_side, "body": m.body, "created_at": m.created_at,
            } for m in msgs
        ],
    })
