from sqlalchemy import (
    Column, String, Boolean, Integer, Text, DateTime, Time, ForeignKey, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class BusinessHour(Base, UUIDPrimaryKey, TimestampMixin):
    """Weekly business hours for the tenant."""
    __tablename__ = "business_hours"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id"), nullable=True, index=True)
    weekday = Column(Integer, nullable=False)   # 0=Mon ... 6=Sun
    open_time = Column(Time, nullable=True)
    close_time = Column(Time, nullable=True)
    break_start_time = Column(Time, nullable=True)
    break_end_time = Column(Time, nullable=True)
    is_closed = Column(Boolean, default=False, nullable=False)

    tenant = relationship("Tenant", back_populates="business_hours")

    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_business_hours_weekday"),
    )


class BlockedTime(Base, UUIDPrimaryKey, TimestampMixin):
    """Blocks for tenant (entire company) or individual professional."""
    __tablename__ = "blocked_times"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    professional_id = Column(UUID(as_uuid=True), ForeignKey("professionals.id", ondelete="CASCADE"), nullable=True, index=True)
    # null = blocks entire tenant

    start_datetime = Column(DateTime(timezone=True), nullable=False)
    end_datetime = Column(DateTime(timezone=True), nullable=False)
    reason = Column(Text)
    block_type = Column(String(30), nullable=False, default="other")
    # tenant | professional | holiday | maintenance | personal | other
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    tenant = relationship("Tenant", back_populates="blocked_times")
    professional = relationship("Professional", back_populates="blocked_times")

    __table_args__ = (
        CheckConstraint("end_datetime > start_datetime", name="ck_blocked_times_datetime_order"),
        CheckConstraint(
            "block_type IN ('tenant','professional','holiday','maintenance','personal','other')",
            name="ck_blocked_times_block_type"
        ),
    )
