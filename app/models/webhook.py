from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class WebhookEndpoint(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "webhook_endpoints"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    url = Column(String(1000), nullable=False)
    secret = Column(String(200), nullable=True)
    event_types = Column(JSONB, nullable=True)  # list of event type strings
    is_active = Column(Boolean, default=True)

    tenant = relationship("Tenant", back_populates="webhook_endpoints")
    deliveries = relationship("WebhookDelivery", back_populates="endpoint", cascade="all, delete-orphan")


class WebhookDelivery(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "webhook_deliveries"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    webhook_endpoint_id = Column(UUID(as_uuid=True), ForeignKey("webhook_endpoints.id", ondelete="CASCADE"), nullable=False)

    event_type = Column(String(80), nullable=False)
    payload = Column(JSONB, nullable=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    # pending | sent | failed | retrying
    response_status = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    attempt_count = Column(Integer, default=0)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)

    endpoint = relationship("WebhookEndpoint", back_populates="deliveries")
