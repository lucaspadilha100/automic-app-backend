"""
Owner notifications — operational alerts for the AUTOMIC platform owner.

These are 1-way alerts (no reply) raised by domain events that the owner
cares about: new tenant signup, cancellation, payment failure, support ticket
opened, etc. They live on the master console as an inbox bell.

Distinct from `NotificationLog` (per-tenant outgoing notifications to its
own customers — emails/SMS/WhatsApp).
"""
import enum
from sqlalchemy import (
    Column, String, Text, ForeignKey, Boolean, DateTime, Index,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base_model import UUIDPrimaryKey, TimestampMixin
from db.base import Base


class OwnerNotificationType(str, enum.Enum):
    tenant_signup = "tenant_signup"
    tenant_cancelled = "tenant_cancelled"
    tenant_suspended = "tenant_suspended"
    tenant_reactivated = "tenant_reactivated"
    tenant_payment_failed = "tenant_payment_failed"
    support_ticket_created = "support_ticket_created"
    support_ticket_replied = "support_ticket_replied"
    custom = "custom"


class OwnerNotificationSeverity(str, enum.Enum):
    info = "info"
    success = "success"
    warning = "warning"
    error = "error"


class OwnerNotification(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "owner_notifications"

    notification_type = Column(
        SAEnum(OwnerNotificationType, name="owner_notification_type", create_type=False),
        nullable=False, index=True,
    )
    severity = Column(
        SAEnum(OwnerNotificationSeverity, name="owner_notification_severity", create_type=False),
        nullable=False, default=OwnerNotificationSeverity.info,
    )
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)

    # Optional links to entities for deep-linking from the inbox
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    related_entity_type = Column(String(50), nullable=True)  # e.g. 'support_ticket'
    related_entity_id = Column(UUID(as_uuid=True), nullable=True)

    # Read state
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)

    # Free-form payload (provider info, error trace, etc)
    payload = Column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_owner_notifications_created_at", "created_at"),
        Index("ix_owner_notifications_unread", "is_read", "created_at"),
    )
