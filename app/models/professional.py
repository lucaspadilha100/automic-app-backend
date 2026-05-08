from sqlalchemy import (
    Column, String, Boolean, Integer, Text, DateTime, Time, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class Professional(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "professionals"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id"), nullable=True, index=True)

    name = Column(String(200), nullable=False)
    bio = Column(Text)
    photo_url = Column(String(500))
    phone = Column(String(30))
    email = Column(String(255))
    is_active = Column(Boolean, default=True, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    tenant = relationship("Tenant", back_populates="professionals")
    user = relationship("User", back_populates="professional")
    professional_services = relationship("ProfessionalService", back_populates="professional", cascade="all, delete-orphan")
    availability = relationship("ProfessionalAvailability", back_populates="professional", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="professional")
    blocked_times = relationship("BlockedTime", back_populates="professional")


class ProfessionalAvailability(Base, UUIDPrimaryKey, TimestampMixin):
    """Weekly schedule for a specific professional."""
    __tablename__ = "professional_availability"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    professional_id = Column(UUID(as_uuid=True), ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False, index=True)

    weekday = Column(Integer, nullable=False)  # 0=Mon ... 6=Sun
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    break_start_time = Column(Time, nullable=True)
    break_end_time = Column(Time, nullable=True)
    is_available = Column(Boolean, default=True, nullable=False)

    professional = relationship("Professional", back_populates="availability")
