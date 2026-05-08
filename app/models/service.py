from sqlalchemy import (
    Column, String, Boolean, Integer, Text, DateTime,
    ForeignKey, UniqueConstraint, CheckConstraint, Numeric
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class ServiceCategory(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "service_categories"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    description = Column(Text)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, nullable=False)

    tenant = relationship("Tenant", back_populates="service_categories")
    services = relationship("Service", back_populates="category")

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_service_categories_tenant_name"),
    )


class Service(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "services"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("service_categories.id"), nullable=True)

    name = Column(String(200), nullable=False)
    description = Column(Text)
    price = Column(Numeric(10, 2), default=0, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    buffer_before_minutes = Column(Integer, default=0, nullable=False)
    buffer_after_minutes = Column(Integer, default=0, nullable=False)
    image_url = Column(String(500))

    requires_deposit = Column(Boolean, default=False, server_default='false', nullable=False)
    deposit_type = Column(String(20), default="none", server_default='none', nullable=False)
    deposit_value = Column(Numeric(10, 2), default=0, server_default='0', nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    tenant = relationship("Tenant", back_populates="services")
    category = relationship("ServiceCategory", back_populates="services")
    professional_services = relationship("ProfessionalService", back_populates="service", cascade="all, delete-orphan")
    appointment_services = relationship("AppointmentService", back_populates="service")
    package_service_links = relationship("PackageService", back_populates="service", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_services_price_non_negative"),
        CheckConstraint("duration_minutes > 0", name="ck_services_duration_positive"),
        CheckConstraint("buffer_before_minutes >= 0", name="ck_services_buffer_before_non_negative"),
        CheckConstraint("buffer_after_minutes >= 0", name="ck_services_buffer_after_non_negative"),
        CheckConstraint("deposit_value >= 0", name="ck_services_deposit_value_non_negative"),
        CheckConstraint("deposit_type IN ('none','fixed','percentage')", name="ck_services_deposit_type"),
    )


class ProfessionalService(Base, UUIDPrimaryKey):
    """M2M: which services a professional can perform."""
    __tablename__ = "professional_services"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    professional_id = Column(UUID(as_uuid=True), ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(UUID(as_uuid=True), ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    professional = relationship("Professional", back_populates="professional_services")
    service = relationship("Service", back_populates="professional_services")

    __table_args__ = (
        UniqueConstraint("tenant_id", "professional_id", "service_id", name="uq_professional_services"),
    )
