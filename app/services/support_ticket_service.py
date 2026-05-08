"""
Service for support tickets.

Conventions:
- Tenant users only ever see their own tenant's tickets (enforced at the route
  via require_active_tenant).
- Super admins see all tickets across all tenants.
- Posting a message updates `last_message_at` and may transition status:
    - Tenant posts on `pending` ticket → status goes back to `open`
    - Super admin posts on `open` ticket → status goes to `pending`
- Tenant-side activity also emits an OwnerNotification so the AUTOMIC owner
  sees a bell on the master inbox. Owner notifications are advisory and
  never break the underlying mutation if they fail.
"""
from datetime import datetime, timezone
from typing import Optional, List
import uuid

from sqlalchemy.orm import Session

from app.models.support_ticket import (
    SupportTicket, SupportTicketMessage,
    SupportTicketStatus, SupportTicketCategory, SupportTicketPriority,
)
from app.models.tenant import Tenant
from app.core.exceptions import NotFoundError, ForbiddenError
from app.services.owner_notification_service import owner_notification_service


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SupportTicketService:
    # ── Creation ────────────────────────────────────────────────────────────
    def create_ticket(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        subject: str,
        body: str,
        category: SupportTicketCategory,
        priority: SupportTicketPriority,
    ) -> SupportTicket:
        ticket = SupportTicket(
            tenant_id=tenant_id,
            created_by_user_id=user_id,
            subject=subject.strip(),
            category=category,
            priority=priority,
            status=SupportTicketStatus.open,
            last_message_at=_utcnow(),
        )
        db.add(ticket)
        db.flush()  # need ticket.id for the message FK

        msg = SupportTicketMessage(
            ticket_id=ticket.id,
            author_user_id=user_id,
            author_side="tenant",
            body=body,
        )
        db.add(msg)
        db.commit()
        db.refresh(ticket)

        # Notify the AUTOMIC owner (best-effort)
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant:
            owner_notification_service.emit_support_ticket_created(
                db,
                ticket_id=ticket.id, tenant_id=tenant_id,
                tenant_name=tenant.name, subject=ticket.subject,
                priority=ticket.priority.value,
            )
            db.commit()
        return ticket

    # ── Listing ─────────────────────────────────────────────────────────────
    def list_tenant_tickets(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        status: Optional[SupportTicketStatus] = None,
    ) -> List[SupportTicket]:
        q = db.query(SupportTicket).filter(SupportTicket.tenant_id == tenant_id)
        if status:
            q = q.filter(SupportTicket.status == status)
        return q.order_by(SupportTicket.created_at.desc()).all()

    def list_all_tickets(
        self,
        db: Session,
        status: Optional[SupportTicketStatus] = None,
        tenant_id: Optional[uuid.UUID] = None,
        priority: Optional[SupportTicketPriority] = None,
        assigned_to: Optional[uuid.UUID] = None,
    ) -> List[SupportTicket]:
        q = db.query(SupportTicket)
        if status:
            q = q.filter(SupportTicket.status == status)
        if tenant_id:
            q = q.filter(SupportTicket.tenant_id == tenant_id)
        if priority:
            q = q.filter(SupportTicket.priority == priority)
        if assigned_to:
            q = q.filter(SupportTicket.assigned_to_user_id == assigned_to)
        return q.order_by(SupportTicket.created_at.desc()).all()

    # ── Get with messages ───────────────────────────────────────────────────
    def get_ticket(
        self,
        db: Session,
        ticket_id: uuid.UUID,
        tenant_id: Optional[uuid.UUID] = None,  # if set, enforce ownership
    ) -> SupportTicket:
        q = db.query(SupportTicket).filter(SupportTicket.id == ticket_id)
        if tenant_id is not None:
            q = q.filter(SupportTicket.tenant_id == tenant_id)
        ticket = q.first()
        if not ticket:
            raise NotFoundError("Ticket não encontrado.")
        return ticket

    def list_messages(self, db: Session, ticket_id: uuid.UUID) -> List[SupportTicketMessage]:
        return (
            db.query(SupportTicketMessage)
            .filter(SupportTicketMessage.ticket_id == ticket_id)
            .order_by(SupportTicketMessage.created_at.asc())
            .all()
        )

    # ── Reply ───────────────────────────────────────────────────────────────
    def add_message(
        self,
        db: Session,
        ticket: SupportTicket,
        author_user_id: Optional[uuid.UUID],
        author_side: str,  # 'tenant' | 'automic'
        body: str,
    ) -> SupportTicketMessage:
        if ticket.status == SupportTicketStatus.closed:
            raise ForbiddenError("Ticket fechado não pode receber novas mensagens.")
        msg = SupportTicketMessage(
            ticket_id=ticket.id,
            author_user_id=author_user_id,
            author_side=author_side,
            body=body,
        )
        db.add(msg)
        ticket.last_message_at = _utcnow()
        # Status transitions
        if author_side == "tenant" and ticket.status == SupportTicketStatus.pending:
            ticket.status = SupportTicketStatus.open
        elif author_side == "automic" and ticket.status == SupportTicketStatus.open:
            ticket.status = SupportTicketStatus.pending
        # If was resolved and tenant replies, reopen
        if author_side == "tenant" and ticket.status == SupportTicketStatus.resolved:
            ticket.status = SupportTicketStatus.open
            ticket.resolved_at = None
        db.add(ticket)
        db.commit()
        db.refresh(msg)

        # Notify owner only on tenant-side replies (avoid self-pings)
        if author_side == "tenant":
            tenant = db.query(Tenant).filter(Tenant.id == ticket.tenant_id).first()
            if tenant:
                owner_notification_service.emit_support_ticket_replied(
                    db,
                    ticket_id=ticket.id, tenant_id=ticket.tenant_id,
                    tenant_name=tenant.name, subject=ticket.subject,
                )
                db.commit()
        return msg

    # ── Master mutations ────────────────────────────────────────────────────
    def set_status(
        self, db: Session, ticket: SupportTicket, new_status: SupportTicketStatus,
    ) -> SupportTicket:
        ticket.status = new_status
        if new_status == SupportTicketStatus.resolved and ticket.resolved_at is None:
            ticket.resolved_at = _utcnow()
        if new_status in (SupportTicketStatus.open, SupportTicketStatus.pending):
            ticket.resolved_at = None
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        return ticket

    def set_priority(
        self, db: Session, ticket: SupportTicket, new_priority: SupportTicketPriority,
    ) -> SupportTicket:
        ticket.priority = new_priority
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        return ticket

    def assign(
        self, db: Session, ticket: SupportTicket, assigned_to_user_id: Optional[uuid.UUID],
    ) -> SupportTicket:
        ticket.assigned_to_user_id = assigned_to_user_id
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        return ticket


support_ticket_service = SupportTicketService()
