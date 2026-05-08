"""
Support routes for the tenant side. Internal users (any role except super_admin)
can open and reply to their own tenant's tickets.
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import (
    require_active_tenant, require_receptionist_or_above,
)
from app.models.user import User
from app.models.tenant import Tenant
from app.models.support_ticket import SupportTicketStatus
from app.schemas.support_ticket import (
    SupportTicketCreate, SupportTicketResponse,
    SupportTicketWithMessagesResponse, SupportTicketMessageResponse,
    SupportTicketMessageCreate,
)
from app.services.support_ticket_service import support_ticket_service

router = APIRouter(prefix="/support/tickets", tags=["Suporte - Tenant"])


@router.get("", response_model=List[SupportTicketResponse])
def list_my_tenant_tickets(
    status: Optional[SupportTicketStatus] = Query(None),
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    return support_ticket_service.list_tenant_tickets(db, tenant.id, status)


@router.post("", response_model=SupportTicketWithMessagesResponse, status_code=201)
def create_ticket(
    payload: SupportTicketCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    ticket = support_ticket_service.create_ticket(
        db=db,
        tenant_id=tenant.id,
        user_id=current_user.id,
        subject=payload.subject,
        body=payload.body,
        category=payload.category,
        priority=payload.priority,
    )
    msgs = support_ticket_service.list_messages(db, ticket.id)
    return _with_messages(ticket, msgs)


@router.get("/{ticket_id}", response_model=SupportTicketWithMessagesResponse)
def get_ticket(
    ticket_id: str,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    ticket = support_ticket_service.get_ticket(db, uuid.UUID(ticket_id), tenant_id=tenant.id)
    msgs = support_ticket_service.list_messages(db, ticket.id)
    return _with_messages(ticket, msgs)


@router.post("/{ticket_id}/messages", response_model=SupportTicketMessageResponse, status_code=201)
def reply_ticket(
    ticket_id: str,
    payload: SupportTicketMessageCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    ticket = support_ticket_service.get_ticket(db, uuid.UUID(ticket_id), tenant_id=tenant.id)
    return support_ticket_service.add_message(
        db=db, ticket=ticket,
        author_user_id=current_user.id,
        author_side="tenant",
        body=payload.body,
    )


def _with_messages(ticket, msgs):
    """Manual assembly to satisfy the WithMessages response model."""
    return SupportTicketWithMessagesResponse.model_validate({
        **{
            "id": ticket.id,
            "tenant_id": ticket.tenant_id,
            "created_by_user_id": ticket.created_by_user_id,
            "assigned_to_user_id": ticket.assigned_to_user_id,
            "subject": ticket.subject,
            "category": ticket.category,
            "priority": ticket.priority,
            "status": ticket.status,
            "last_message_at": ticket.last_message_at,
            "resolved_at": ticket.resolved_at,
            "created_at": ticket.created_at,
            "updated_at": ticket.updated_at,
        },
        "messages": [
            {
                "id": m.id, "ticket_id": m.ticket_id, "author_user_id": m.author_user_id,
                "author_side": m.author_side, "body": m.body, "created_at": m.created_at,
            } for m in msgs
        ],
    })
