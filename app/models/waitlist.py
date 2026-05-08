from sqlalchemy import Column, String, Date, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class WaitlistEntry(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "waitlist_entries"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_account_id = Column(UUID(as_uuid=True), ForeignKey("customer_accounts.id"), nullable=False, index=True)
    tenant_customer_id = Column(UUID(as_uuid=True), ForeignKey("tenant_customers.id"), nullable=True)

    service_ids = Column(JSONB, nullable=True)
    preferred_professional_id = Column(UUID(as_uuid=True), ForeignKey("professionals.id"), nullable=True)
    preferred_date = Column(Date, nullable=True)
    preferred_period = Column(String(20), nullable=True)  # morning | afternoon | evening | any

    status = Column(String(20), nullable=False, default="waiting")
    # waiting | notified | converted | cancelled

    __table_args__ = (
        CheckConstraint("status IN ('waiting','notified','converted','cancelled')", name="ck_waitlist_status"),
    )
