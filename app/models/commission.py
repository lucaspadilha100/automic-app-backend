import enum
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Numeric, Enum as SAEnum, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class CommissionType(str, enum.Enum):
    percentage = "percentage"
    fixed = "fixed"
    none = "none"


class CommissionStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    cancelled = "cancelled"


class ProfessionalCommissionSetting(Base, UUIDPrimaryKey, TimestampMixin):
    """Commission configuration per professional per tenant."""
    __tablename__ = "professional_commission_settings"

    __table_args__ = (
        CheckConstraint("commission_value >= 0", name="ck_commission_settings_value_non_negative"),
    )

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    professional_id = Column(UUID(as_uuid=True), ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False, index=True)
    commission_type = Column(
        SAEnum(CommissionType, name="commission_type_enum", create_type=False),
        nullable=False,
        default=CommissionType.none,
    )
    commission_value = Column(Numeric(10, 2), nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    professional = relationship("Professional")


class CommissionRecord(Base, UUIDPrimaryKey, TimestampMixin):
    """Auto-generated commission record when an appointment is completed."""
    __tablename__ = "commission_records"

    __table_args__ = (
        CheckConstraint("base_amount >= 0", name="ck_commission_records_base_non_negative"),
        CheckConstraint("commission_value >= 0", name="ck_commission_records_value_non_negative"),
        CheckConstraint("commission_amount >= 0", name="ck_commission_records_amount_non_negative"),
    )

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    professional_id = Column(UUID(as_uuid=True), ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False, index=True)
    base_amount = Column(Numeric(10, 2), nullable=False, default=0)
    commission_type = Column(
        SAEnum(CommissionType, name="commission_type_enum", create_type=False),
        nullable=False,
    )
    commission_value = Column(Numeric(10, 2), nullable=False, default=0)
    commission_amount = Column(Numeric(10, 2), nullable=False, default=0)
    status = Column(
        SAEnum(CommissionStatus, name="commission_status_enum", create_type=False),
        nullable=False,
        default=CommissionStatus.pending,
        index=True,
    )

    professional = relationship("Professional")
    appointment = relationship("Appointment")
