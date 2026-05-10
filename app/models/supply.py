from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime, ForeignKey, CheckConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class Supply(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "supplies"
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    unit = Column(String(20), nullable=False, default="un")  # un, ml, g, kg, l
    cost_price = Column(Numeric(10, 2), default=0, nullable=False)
    track_stock = Column(Boolean, default=False, nullable=False)
    stock_quantity = Column(Numeric(10, 3), default=0, nullable=False)
    low_stock_threshold = Column(Numeric(10, 3), default=5, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    tenant = relationship("Tenant", back_populates="supplies")
    usage_records = relationship("AppointmentSupplyUsage", back_populates="supply")


class AppointmentSupplyUsage(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "appointment_supply_usage"
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    supply_id = Column(UUID(as_uuid=True), ForeignKey("supplies.id"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity_used = Column(Numeric(10, 3), nullable=False)
    notes = Column(Text)
    supply = relationship("Supply", back_populates="usage_records")
    appointment = relationship("Appointment", back_populates="supply_usages")
