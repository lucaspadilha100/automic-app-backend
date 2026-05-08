import enum
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class ActionType(str, enum.Enum):
    add_customer_tag = "add_customer_tag"
    create_customer_note = "create_customer_note"
    emit_webhook_event = "emit_webhook_event"
    create_notification_log = "create_notification_log"


class AutomationRule(Base, UUIDPrimaryKey, TimestampMixin):
    """Tenant-scoped automation rule triggered by customer events."""
    __tablename__ = "automation_rules"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    trigger_event = Column(String(100), nullable=False, index=True)
    conditions = Column(JSONB, nullable=True)   # dict of field -> expected_value
    action_type = Column(
        SAEnum(ActionType, name="automation_action_type_enum", create_type=False),
        nullable=False,
        index=True,
    )
    action_config = Column(JSONB, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
