from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import UUIDPrimaryKey


class CustomerEvent(Base, UUIDPrimaryKey):
    """Event bus for CRM, automations and future integrations."""
    __tablename__ = "customer_events"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_account_id = Column(UUID(as_uuid=True), ForeignKey("customer_accounts.id"), nullable=True, index=True)
    tenant_customer_id = Column(UUID(as_uuid=True), ForeignKey("tenant_customers.id"), nullable=True)

    event_type = Column(String(80), nullable=False, index=True)
    # customer_created | appointment_created | appointment_completed | payment_confirmed | ...
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    customer_account = relationship("CustomerAccount", back_populates="customer_events")
