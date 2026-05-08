from sqlalchemy import Column, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class TenantLifecycleSetting(Base, UUIDPrimaryKey, TimestampMixin):
    """Per-tenant configuration for customer lifecycle thresholds."""
    __tablename__ = "tenant_lifecycle_settings"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
                       nullable=False, unique=True, index=True)

    inactive_after_days = Column(Integer, nullable=False, default=90)
    at_risk_after_days = Column(Integer, nullable=False, default=45)
    recurring_min_appointments = Column(Integer, nullable=False, default=3)
    vip_min_appointments = Column(Integer, nullable=False, default=5)
    vip_min_total_spent = Column(Numeric(12, 2), nullable=False, default=1000)
