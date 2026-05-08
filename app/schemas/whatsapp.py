from pydantic import BaseModel, ConfigDict, field_validator, AnyHttpUrl
from typing import Optional
from datetime import datetime
import uuid

from app.models.whatsapp import WhatsAppStatus, WhatsAppProvider, WhatsAppConnectionType

VALID_STATUSES = {s.value for s in WhatsAppStatus}
VALID_PROVIDERS = {p.value for p in WhatsAppProvider}
VALID_CONNECTION_TYPES = {ct.value for ct in WhatsAppConnectionType}


class TenantWhatsAppSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    provider: Optional[str] = None
    connection_type: Optional[str] = None
    webhook_url: Optional[str] = None
    instance_id: Optional[str] = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_PROVIDERS:
            raise ValueError(f"provider inválido. Aceitos: {sorted(VALID_PROVIDERS)}")
        return v

    @field_validator("connection_type")
    @classmethod
    def validate_connection_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_CONNECTION_TYPES:
            raise ValueError(f"connection_type inválido. Aceitos: {sorted(VALID_CONNECTION_TYPES)}")
        return v

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v != "":
            if not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("webhook_url deve ser uma URL válida começando com http:// ou https://")
        return v


class TenantWhatsAppSettingsResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    enabled: bool
    provider: Optional[str]
    connection_type: Optional[str]
    webhook_url: Optional[str]
    instance_id: Optional[str]
    status: str
    last_connected_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TenantWhatsAppStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"status inválido. Aceitos: {sorted(VALID_STATUSES)}")
        return v


class TenantWhatsAppStatusResponse(BaseModel):
    tenant_id: uuid.UUID
    enabled: bool
    status: str
    provider: Optional[str]
    last_connected_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
