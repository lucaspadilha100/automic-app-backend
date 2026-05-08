from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime, ForeignKey, Numeric, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class AppointmentReview(Base, UUIDPrimaryKey):
    __tablename__ = "appointment_reviews"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_account_id = Column(UUID(as_uuid=True), ForeignKey("customer_accounts.id"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    visibility = Column(String(30), default="customer_visible", nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    appointment = relationship("Appointment")
    customer_account = relationship("CustomerAccount")

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_appointment_reviews_rating_range"),
        CheckConstraint("visibility IN ('internal','public','customer_visible')", name="ck_appointment_reviews_visibility"),
    )


class Coupon(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "coupons"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(100), nullable=False)
    discount_type = Column(String(20), nullable=False)
    discount_value = Column(Numeric(10, 2), nullable=False, default=0)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    usage_limit = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_coupons_tenant_code"),
        CheckConstraint("discount_type IN ('fixed','percentage')", name="ck_coupons_discount_type"),
        CheckConstraint("discount_value >= 0", name="ck_coupons_discount_value_non_negative"),
        CheckConstraint("usage_limit IS NULL OR usage_limit >= 0", name="ck_coupons_usage_limit_non_negative"),
    )


class AppointmentHold(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "appointment_holds"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_account_id = Column(UUID(as_uuid=True), ForeignKey("customer_accounts.id"), nullable=True, index=True)
    professional_id = Column(UUID(as_uuid=True), ForeignKey("professionals.id"), nullable=False, index=True)
    start_datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    end_datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    service_ids = Column(JSONB, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), default="active", nullable=False)

    __table_args__ = (
        CheckConstraint("end_datetime > start_datetime", name="ck_appointment_holds_datetime_order"),
        CheckConstraint("status IN ('active','expired','converted','cancelled')", name="ck_appointment_holds_status"),
    )
