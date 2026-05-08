from sqlalchemy import (
    Column, String, Boolean, Text, DateTime, ForeignKey, Numeric, Integer,
    UniqueConstraint, Date
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class CustomerAccount(Base, UUIDPrimaryKey, TimestampMixin):
    """Global customer account - shared across tenants."""
    __tablename__ = "customer_accounts"

    name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=True, unique=True, index=True)
    phone = Column(String(30), nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    phone_verified_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant_customers = relationship("TenantCustomer", back_populates="customer_account", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="customer_account")
    customer_events = relationship("CustomerEvent", back_populates="customer_account")
    customer_packages = relationship("CustomerPackage", back_populates="customer_account")


class TenantCustomer(Base, UUIDPrimaryKey, TimestampMixin):
    """Link between a global customer and a specific tenant."""
    __tablename__ = "tenant_customers"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_account_id = Column(UUID(as_uuid=True), ForeignKey("customer_accounts.id", ondelete="CASCADE"), nullable=False, index=True)

    cpf = Column(String(20), nullable=True)
    birth_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)           # visible to customer
    internal_notes = Column(Text, nullable=True)  # staff only
    marketing_consent = Column(Boolean, default=False)
    terms_accepted_at = Column(DateTime(timezone=True), nullable=True)
    privacy_policy_accepted_at = Column(DateTime(timezone=True), nullable=True)
    data_processing_consent_at = Column(DateTime(timezone=True), nullable=True)

    # Lifecycle fields
    lifecycle_status = Column(String(20), nullable=False, default="new")
    last_appointment_at = Column(DateTime(timezone=True), nullable=True)
    next_appointment_at = Column(DateTime(timezone=True), nullable=True)
    total_spent = Column(Numeric(12, 2), nullable=False, default=0)
    appointments_count = Column(Integer, nullable=False, default=0)
    no_show_count = Column(Integer, nullable=False, default=0)

    customer_account = relationship("CustomerAccount", back_populates="tenant_customers")
    appointments = relationship("Appointment", back_populates="tenant_customer")
    procedure_history = relationship("ProcedureHistory", back_populates="tenant_customer")
    customer_packages = relationship("CustomerPackage", back_populates="tenant_customer")
    tags = relationship("CustomerTagLink", back_populates="tenant_customer", cascade="all, delete-orphan")
    customer_notes = relationship("CustomerNote", back_populates="tenant_customer", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "customer_account_id", name="uq_tenant_customers_tenant_customer"),
    )


class CustomerTag(Base, UUIDPrimaryKey, TimestampMixin):
    """Tag definitions per tenant for customer segmentation."""
    __tablename__ = "customer_tags"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    color = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_customer_tags_tenant_name"),
    )


class CustomerTagLink(Base, UUIDPrimaryKey):
    """M2M: tag applied to a tenant_customer."""
    __tablename__ = "customer_tag_links"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_customer_id = Column(UUID(as_uuid=True), ForeignKey("tenant_customers.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_id = Column(UUID(as_uuid=True), ForeignKey("customer_tags.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    tenant_customer = relationship("TenantCustomer", back_populates="tags")

    __table_args__ = (
        UniqueConstraint("tenant_customer_id", "tag_id", name="uq_customer_tag_links"),
    )


class CustomerNote(Base, UUIDPrimaryKey, TimestampMixin):
    """Timeline/notes for a customer within a tenant."""
    __tablename__ = "customer_notes"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_customer_id = Column(UUID(as_uuid=True), ForeignKey("tenant_customers.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    content = Column(Text, nullable=False)
    note = Column(Text, nullable=False)  # prompt-compatible alias for content
    is_internal = Column(Boolean, default=True)  # True = staff only, False = visible to customer
    visibility = Column(String(30), default="internal", nullable=False)  # internal | customer_visible
    note_type = Column(String(50), default="manual")
    # manual | system | appointment | payment | package

    tenant_customer = relationship("TenantCustomer", back_populates="customer_notes")
