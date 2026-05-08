"""
Support tickets — communication channel between tenants and the AUTOMIC owner.

A ticket is opened by any internal user of a tenant (tenant_owner / manager /
receptionist) and forms a thread of messages. Both sides (tenant users and
super_admins) can post messages. Status drives the inbox UX on the master side.

Distinct from notifications: a ticket is a 2-way conversation, a notification
is a 1-way alert.
"""
import enum
from sqlalchemy import (
    Column, String, Text, ForeignKey, Index, Enum as SAEnum, DateTime,
)
from sqlalchemy.dialects.postgresql import UUID

from app.models.base_model import UUIDPrimaryKey, TimestampMixin
from db.base import Base


class SupportTicketStatus(str, enum.Enum):
    open = "open"            # Aberto, aguarda primeira resposta do AUTOMIC
    pending = "pending"      # AUTOMIC respondeu, aguarda tenant
    resolved = "resolved"    # Resolvido, mas pode reabrir
    closed = "closed"        # Fechado definitivamente, não reabre


class SupportTicketCategory(str, enum.Enum):
    bug = "bug"
    question = "question"
    billing = "billing"
    feature_request = "feature_request"
    other = "other"


class SupportTicketPriority(str, enum.Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class SupportTicket(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "support_tickets"

    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Quem abriu (user interno do tenant)
    created_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    # Super admin atualmente atribuído (opcional)
    assigned_to_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    subject = Column(String(255), nullable=False)
    category = Column(
        SAEnum(SupportTicketCategory, name="support_ticket_category", create_type=False),
        nullable=False, default=SupportTicketCategory.question,
    )
    priority = Column(
        SAEnum(SupportTicketPriority, name="support_ticket_priority", create_type=False),
        nullable=False, default=SupportTicketPriority.normal,
    )
    status = Column(
        SAEnum(SupportTicketStatus, name="support_ticket_status", create_type=False),
        nullable=False, default=SupportTicketStatus.open, index=True,
    )

    # Auxiliar pra UI (último contato e resolved_at)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_support_tickets_tenant_status", "tenant_id", "status"),
    )


class SupportTicketMessage(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "support_ticket_messages"

    ticket_id = Column(
        UUID(as_uuid=True), ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Autor: user interno (do tenant) ou super_admin (AUTOMIC)
    author_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    # Snapshot do papel no momento da escrita ('tenant', 'automic')
    author_side = Column(String(20), nullable=False, default="tenant")
    body = Column(Text, nullable=False)
