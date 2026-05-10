from sqlalchemy import Column, String, DateTime, ForeignKey, Numeric, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class Payment(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "payments"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_account_id = Column(UUID(as_uuid=True), ForeignKey("customer_accounts.id"), nullable=True)
    registered_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    # pending | paid | failed | refunded | cancelled

    payment_method = Column(String(30), default="none")
    # none | pix_manual | pix_gateway | credit_card | debit_card | cash | other

    provider = Column(String(50), nullable=True)
    provider_payment_id = Column(String(200), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    appointment = relationship("Appointment", back_populates="payments")
    customer_account = relationship("CustomerAccount")
    registered_by = relationship("User", foreign_keys=[registered_by_user_id])

    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_payments_amount_non_negative"),
        CheckConstraint("status IN ('pending','paid','failed','refunded','cancelled')", name="ck_payments_status"),
        CheckConstraint(
            "payment_method IN ('none','pix_manual','pix_gateway','credit_card','debit_card','cash','other')",
            name="ck_payments_method"
        ),
    )

