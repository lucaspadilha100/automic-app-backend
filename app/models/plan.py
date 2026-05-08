import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, Numeric, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class Plan(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "plans"

    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    price_monthly = Column(Numeric(10, 2), default=0)

    # Limits (None = unlimited)
    max_services = Column(Integer, nullable=True)
    max_professionals = Column(Integer, nullable=True)
    max_users = Column(Integer, nullable=True)
    max_appointments_per_month = Column(Integer, nullable=True)
    max_units = Column(Integer, default=1)
    max_packages = Column(Integer, nullable=True)

    # Feature flags (boolean)
    allow_online_payment = Column(Boolean, default=False)
    allow_packages = Column(Boolean, default=True)
    allow_custom_terms = Column(Boolean, default=False)
    allow_advanced_reports = Column(Boolean, default=False)
    allow_crm_integration = Column(Boolean, default=False)
    allow_before_after_photos = Column(Boolean, default=False)
    allow_multi_unit = Column(Boolean, default=False)
    allow_waitlist = Column(Boolean, default=False)
    allow_physical_resources = Column(Boolean, default=False)
    allow_webhooks = Column(Boolean, default=False)
    allow_custom_forms = Column(Boolean, default=False)
    allow_customer_lifecycle = Column(Boolean, default=False)
    allow_automation_rules = Column(Boolean, default=False)
    allow_whatsapp_integration = Column(Boolean, default=False)
    allow_commissions = Column(Boolean, default=False)

    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    subscriptions = relationship("TenantSubscription", back_populates="plan")
