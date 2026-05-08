from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class Unit(Base, UUIDPrimaryKey, TimestampMixin):
    """Branch/unit of a tenant. MVP has one main unit."""
    __tablename__ = "units"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    address = Column(Text)
    phone = Column(String(30))
    whatsapp = Column(String(30))
    email = Column(String(255))
    timezone = Column(String(60), nullable=True)
    is_main = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    tenant = relationship("Tenant", back_populates="units")
