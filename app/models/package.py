from sqlalchemy import (
    Column, String, Boolean, Integer, Text, DateTime,
    ForeignKey, Numeric, CheckConstraint, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class Package(Base, UUIDPrimaryKey, TimestampMixin):
    """Session package offered by a tenant (e.g. 10x drainage, 5x massage)."""
    __tablename__ = "packages"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    total_sessions = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False, default=0)
    validity_days = Column(Integer, nullable=True)  # None = no expiry
    service_ids = Column(JSONB, nullable=True)  # list of service_id UUIDs allowed

    is_active = Column(Boolean, default=True, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    tenant = relationship("Tenant", back_populates="packages")
    customer_packages = relationship("CustomerPackage", back_populates="package")
    package_service_links = relationship("PackageService", back_populates="package", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("total_sessions > 0", name="ck_packages_total_sessions_positive"),
        CheckConstraint("price >= 0", name="ck_packages_price_non_negative"),
    )


class PackageService(Base, UUIDPrimaryKey):
    """Relational mapping of services included in a package."""
    __tablename__ = "package_services"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    package_id = Column(UUID(as_uuid=True), ForeignKey("packages.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(UUID(as_uuid=True), ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    package = relationship("Package", back_populates="package_service_links")
    service = relationship("Service", back_populates="package_service_links")

    __table_args__ = (
        UniqueConstraint("tenant_id", "package_id", "service_id", name="uq_package_services_tenant_package_service"),
    )


class CustomerPackage(Base, UUIDPrimaryKey, TimestampMixin):
    """A package purchased/assigned to a specific customer in a tenant."""
    __tablename__ = "customer_packages"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_account_id = Column(UUID(as_uuid=True), ForeignKey("customer_accounts.id"), nullable=False, index=True)
    tenant_customer_id = Column(UUID(as_uuid=True), ForeignKey("tenant_customers.id"), nullable=False, index=True)
    package_id = Column(UUID(as_uuid=True), ForeignKey("packages.id"), nullable=False)

    total_sessions = Column(Integer, nullable=False)
    used_sessions = Column(Integer, nullable=False, default=0)
    remaining_sessions = Column(Integer, nullable=False)

    status = Column(String(20), nullable=False, default="active")
    # active | fully_used | expired | cancelled | completed(legacy)

    payment_status = Column(String(20), nullable=False, default="pending")
    # pending | paid | failed | refunded | cancelled

    price_paid = Column(Numeric(10, 2), nullable=True)  # legacy name
    purchase_price = Column(Numeric(10, 2), nullable=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)

    package = relationship("Package", back_populates="customer_packages")
    customer_account = relationship("CustomerAccount", back_populates="customer_packages")
    tenant_customer = relationship("TenantCustomer", back_populates="customer_packages")
    sessions = relationship("PackageSession", back_populates="customer_package", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="customer_package", foreign_keys="Appointment.customer_package_id")

    __table_args__ = (
        CheckConstraint("remaining_sessions >= 0", name="ck_customer_packages_remaining_non_negative"),
        CheckConstraint("used_sessions >= 0", name="ck_customer_packages_used_non_negative"),
        CheckConstraint("status IN ('active','fully_used','completed','expired','cancelled')", name="ck_customer_packages_status"),
        CheckConstraint(
            "payment_status IN ('pending','paid','partially_paid','failed','refunded','cancelled')",
            name="ck_customer_packages_payment_status"
        ),
    )


class PackageSession(Base, UUIDPrimaryKey, TimestampMixin):
    """Individual session record for a customer package."""
    __tablename__ = "package_sessions"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_package_id = Column(UUID(as_uuid=True), ForeignKey("customer_packages.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=True)
    service_id = Column(UUID(as_uuid=True), ForeignKey("services.id"), nullable=True)

    action = Column(String(20), nullable=False)
    # legacy: reserved | consumed | returned | cancelled
    status = Column(String(20), nullable=True)
    # prompt-compatible: reserved | used | cancelled

    notes = Column(Text, nullable=True)

    customer_package = relationship("CustomerPackage", back_populates="sessions")

    __table_args__ = (
        CheckConstraint("action IN ('reserved','consumed','returned','cancelled')", name="ck_package_sessions_action"),
        CheckConstraint("status IS NULL OR status IN ('reserved','used','cancelled')", name="ck_package_sessions_status"),
    )
