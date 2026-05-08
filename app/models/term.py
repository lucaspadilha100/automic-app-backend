import enum
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class TermType(str, enum.Enum):
    general = "general"
    procedure = "procedure"
    image_authorization = "image_authorization"
    privacy_policy = "privacy_policy"
    post_procedure = "post_procedure"


class TenantTerm(Base, UUIDPrimaryKey, TimestampMixin):
    """Term document belonging to a tenant."""
    __tablename__ = "tenant_terms"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    term_type = Column(SAEnum(TermType, name="term_type_enum", create_type=False), nullable=False, index=True)
    version = Column(String(50), nullable=False, default="1.0")
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    tenant = relationship("Tenant", back_populates="terms")
    acceptances = relationship("CustomerTermAcceptance", back_populates="term", cascade="all, delete-orphan")


class CustomerTermAcceptance(Base, UUIDPrimaryKey):
    """Records a customer's acceptance of a specific term version."""
    __tablename__ = "customer_term_acceptances"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_account_id = Column(UUID(as_uuid=True), ForeignKey("customer_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_customer_id = Column(UUID(as_uuid=True), ForeignKey("tenant_customers.id", ondelete="SET NULL"), nullable=True)
    term_id = Column(UUID(as_uuid=True), ForeignKey("tenant_terms.id", ondelete="CASCADE"), nullable=False, index=True)
    accepted_at = Column(DateTime(timezone=True), nullable=False)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    term = relationship("TenantTerm", back_populates="acceptances")
    customer_account = relationship("CustomerAccount")
