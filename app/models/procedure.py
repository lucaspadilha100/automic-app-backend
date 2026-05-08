from sqlalchemy import Column, String, Text, DateTime, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class ProcedureHistory(Base, UUIDPrimaryKey, TimestampMixin):
    """Record of a completed procedure for a customer within a tenant."""
    __tablename__ = "procedure_history"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_customer_id = Column(UUID(as_uuid=True), ForeignKey("tenant_customers.id"), nullable=False, index=True)
    customer_account_id = Column(UUID(as_uuid=True), ForeignKey("customer_accounts.id"), nullable=True)
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=True)
    professional_id = Column(UUID(as_uuid=True), ForeignKey("professionals.id"), nullable=True)
    service_id = Column(UUID(as_uuid=True), ForeignKey("services.id"), nullable=True)

    title = Column(String(200), nullable=False)
    description = Column(Text)
    procedure_date = Column(DateTime(timezone=True), nullable=False)
    public_notes = Column(Text)    # visible to customer
    internal_notes = Column(Text)  # staff only
    recommended_return_date = Column(Date, nullable=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    tenant_customer = relationship("TenantCustomer", back_populates="procedure_history")
    appointment = relationship("Appointment", back_populates="procedure_history")
    photos = relationship("ProcedurePhoto", back_populates="procedure_history", cascade="all, delete-orphan")
