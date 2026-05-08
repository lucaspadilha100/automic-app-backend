from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class NotificationTemplate(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "notification_templates"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(80), nullable=False)
    channel = Column(String(20), nullable=False)  # whatsapp | email | sms | internal
    subject = Column(String(300), nullable=True)
    body = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        CheckConstraint("channel IN ('whatsapp','email','sms','internal')", name="ck_notif_templates_channel"),
    )


class NotificationLog(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "notification_logs"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_account_id = Column(UUID(as_uuid=True), ForeignKey("customer_accounts.id"), nullable=True)
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=True)

    channel = Column(String(20), nullable=False)
    event_type = Column(String(80), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    # pending | sent | failed | skipped
    provider = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
