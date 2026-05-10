from sqlalchemy import Column, String, Boolean, Integer, Text, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class Supply(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "supplies"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    unit = Column(String(20), nullable=False, default="un")
    cost_price = Column(Numeric(10, 2), nullable=True)
    track_stock = Column(Boolean, default=False, nullable=False)
    stock_quantity = Column(Numeric(10, 3), nullable=True)
    low_stock_threshold = Column(Numeric(10, 3), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    usages = relationship("AppointmentSupplyUsage", back_populates="supply")


class AppointmentSupplyUsage(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "appointment_supply_usages"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    supply_id = Column(UUID(as_uuid=True), ForeignKey("supplies.id", ondelete="CASCADE"), nullable=False)
    quantity_used = Column(Numeric(10, 3), nullable=False)
    notes = Column(Text, nullable=True)

    supply = relationship("Supply", back_populates="usages")
