import enum
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class WhatsAppStatus(str, enum.Enum):
    disconnected = "disconnected"
    connected = "connected"
    waiting_qr = "waiting_qr"
    error = "error"


class WhatsAppProvider(str, enum.Enum):
    n8n = "n8n"
    evolution_api = "evolution_api"
    zapi = "zapi"
    meta = "meta"
    other = "other"


class WhatsAppConnectionType(str, enum.Enum):
    webhook = "webhook"
    api_key = "api_key"
    qr_code = "qr_code"
    manual = "manual"


class TenantWhatsAppSettings(Base, UUIDPrimaryKey, TimestampMixin):
    """WhatsApp/n8n integration configuration per tenant (one record per tenant)."""
    __tablename__ = "tenant_whatsapp_settings"

    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_tenant_whatsapp_settings_tenant"),
        CheckConstraint(
            "status IN ('disconnected','connected','waiting_qr','error')",
            name="ck_tenant_whatsapp_settings_status",
        ),
    )

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
                       nullable=False, unique=True, index=True)
    enabled = Column(Boolean, nullable=False, default=False)
    provider = Column(String(50), nullable=True)
    connection_type = Column(String(50), nullable=True)
    webhook_url = Column(String(1000), nullable=True)
    instance_id = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="disconnected")
    last_connected_at = Column(DateTime(timezone=True), nullable=True)
