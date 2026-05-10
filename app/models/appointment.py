from sqlalchemy import (
    Column, String, Boolean, Integer, Text, DateTime, ForeignKey,
    Numeric, CheckConstraint, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class Appointment(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "appointments"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_customer_id = Column(UUID(as_uuid=True), ForeignKey("tenant_customers.id"), nullable=True, index=True)
    customer_account_id = Column(UUID(as_uuid=True), ForeignKey("customer_accounts.id"), nullable=True, index=True)
    professional_id = Column(UUID(as_uuid=True), ForeignKey("professionals.id"), nullable=False, index=True)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id"), nullable=True)

    start_datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    end_datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    total_duration_minutes = Column(Integer, nullable=False)
    total_price = Column(Numeric(10, 2), default=0)

    status = Column(String(30), nullable=False, default="scheduled", index=True)
    # draft | pending_payment | scheduled | confirmed | in_progress | completed | cancelled | no_show | rescheduled

    payment_status = Column(String(20), nullable=False, default="not_required")
    # not_required | pending | paid | failed | refunded | cancelled

    source = Column(String(30), default="admin_panel")
    # public_page | admin_panel | whatsapp | instagram | google | manual | campaign | other

    customer_notes = Column(Text)
    internal_notes = Column(Text)
    cancellation_reason = Column(Text)
    cancelled_by_type = Column(String(20))   # customer | staff | system
    cancelled_by_id = Column(UUID(as_uuid=True), nullable=True)

    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    no_show_at = Column(DateTime(timezone=True), nullable=True)

    # Package session link
    customer_package_id = Column(UUID(as_uuid=True), ForeignKey("customer_packages.id"), nullable=True)
    uses_package = Column(Boolean, default=False, nullable=False)

    # Reschedule chain — when an appointment is rescheduled, the new appointment
    # links back to the old one via rescheduled_from_id. The old appointment
    # is marked status='rescheduled' and rescheduled_to_id points to the new.
    # This lets us trace: old -> new -> newer in case of multiple reschedules.
    rescheduled_from_id = Column(
        UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=True, index=True,
    )
    rescheduled_to_id = Column(
        UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=True, index=True,
    )

    tenant = relationship("Tenant", back_populates="appointments")
    tenant_customer = relationship("TenantCustomer", back_populates="appointments")
    customer_account = relationship("CustomerAccount", back_populates="appointments")
    professional = relationship("Professional", back_populates="appointments")
    appointment_services = relationship("AppointmentService", back_populates="appointment", cascade="all, delete-orphan")
    status_history = relationship("AppointmentStatusHistory", back_populates="appointment", cascade="all, delete-orphan")
    procedure_history = relationship("ProcedureHistory", back_populates="appointment", uselist=False)
    payments = relationship("Payment", back_populates="appointment")
    customer_package = relationship("CustomerPackage", back_populates="appointments", foreign_keys=[customer_package_id])
    supply_usages = relationship("AppointmentSupplyUsage", back_populates="appointment", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("end_datetime > start_datetime", name="ck_appointments_datetime_order"),
        CheckConstraint("total_price >= 0", name="ck_appointments_price_non_negative"),
        CheckConstraint(
            "status IN ('draft','pending_payment','scheduled','confirmed','in_progress','completed','cancelled','no_show','rescheduled')",
            name="ck_appointments_status"
        ),
        CheckConstraint(
            "payment_status IN ('not_required','pending','paid','failed','refunded','cancelled')",
            name="ck_appointments_payment_status"
        ),
    )


class AppointmentService(Base, UUIDPrimaryKey):
    """Services included in an appointment (with price/duration snapshots)."""
    __tablename__ = "appointment_services"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(UUID(as_uuid=True), ForeignKey("services.id"), nullable=True)  # null if service deleted
    package_session_id = Column(UUID(as_uuid=True), ForeignKey("package_sessions.id"), nullable=True)

    service_name_snapshot = Column(String(200), nullable=False)
    service_price_snapshot = Column(Numeric(10, 2), nullable=False)
    service_duration_snapshot = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    appointment = relationship("Appointment", back_populates="appointment_services")
    service = relationship("Service", back_populates="appointment_services")
    package_session = relationship("PackageSession")


class AppointmentStatusHistory(Base, UUIDPrimaryKey):
    """Audit trail for appointment status changes."""
    __tablename__ = "appointment_status_history"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status = Column(String(30), nullable=True)
    to_status = Column(String(30), nullable=False)
    # Prompt-compatible aliases. Existing from_status/to_status kept for backward compatibility.
    old_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=True)
    changed_by_type = Column(String(20))  # user | customer | system
    changed_by_id = Column(UUID(as_uuid=True), nullable=True)
    changed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    changed_by_customer_id = Column(UUID(as_uuid=True), ForeignKey("customer_accounts.id"), nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    appointment = relationship("Appointment", back_populates="status_history")


class IdempotencyKey(Base, UUIDPrimaryKey):
    """Prevents duplicate appointments from double-clicks or retries."""
    __tablename__ = "idempotency_keys"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_account_id = Column(UUID(as_uuid=True), ForeignKey("customer_accounts.id"), nullable=True)
    key = Column(String(200), nullable=False)
    request_hash = Column(String(64), nullable=True)
    response_body = Column(JSONB, nullable=True)
    status = Column(String(20), default="processing")
    created_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "key", name="uq_idempotency_keys_tenant_key"),
    )
