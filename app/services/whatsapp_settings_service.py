from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.whatsapp import TenantWhatsAppSettings
from app.services.audit_service import audit_service
from app.services.feature_flag_service import feature_flag_service

FEATURE_KEY = "whatsapp_integration"


class WhatsAppSettingsService:

    def _require_feature(self, db: Session, tenant) -> None:
        feature_flag_service.require_feature(db, tenant, FEATURE_KEY)

    def _get_or_create(self, db: Session, tenant_id: UUID) -> TenantWhatsAppSettings:
        settings = db.query(TenantWhatsAppSettings).filter(
            TenantWhatsAppSettings.tenant_id == tenant_id
        ).first()
        if not settings:
            settings = TenantWhatsAppSettings(
                tenant_id=tenant_id,
                enabled=False,
                status="disconnected",
            )
            db.add(settings)
            db.flush()
        return settings

    def get_settings(self, db: Session, tenant) -> TenantWhatsAppSettings:
        self._require_feature(db, tenant)
        return self._get_or_create(db, tenant.id)

    def upsert_settings(
        self,
        db: Session,
        tenant,
        data: dict,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> TenantWhatsAppSettings:
        self._require_feature(db, tenant)
        settings = self._get_or_create(db, tenant.id)

        old_values = {
            "enabled": settings.enabled,
            "provider": settings.provider,
            "connection_type": settings.connection_type,
            "status": settings.status,
        }

        for k, v in data.items():
            if v is not None:
                setattr(settings, k, v)

        db.flush()

        # Audit — never log webhook_url, instance_id or other sensitive fields
        audit_service.log(
            db=db,
            action="whatsapp_settings_updated",
            entity_type="tenant_whatsapp_settings",
            entity_id=settings.id,
            tenant_id=tenant.id,
            user_id=user_id,
            old_values=old_values,
            new_values={
                "enabled": settings.enabled,
                "provider": settings.provider,
                "connection_type": settings.connection_type,
                "status": settings.status,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.commit()
        db.refresh(settings)
        return settings

    def get_status(self, db: Session, tenant) -> TenantWhatsAppSettings:
        self._require_feature(db, tenant)
        return self._get_or_create(db, tenant.id)

    def update_status(
        self,
        db: Session,
        tenant,
        status: str,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> TenantWhatsAppSettings:
        self._require_feature(db, tenant)
        settings = self._get_or_create(db, tenant.id)
        old_status = settings.status
        settings.status = status

        if status == "connected":
            settings.last_connected_at = datetime.now(timezone.utc)

        db.flush()
        audit_service.log(
            db=db,
            action="whatsapp_status_updated",
            entity_type="tenant_whatsapp_settings",
            entity_id=settings.id,
            tenant_id=tenant.id,
            user_id=user_id,
            old_values={"status": old_status},
            new_values={"status": status},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.commit()
        db.refresh(settings)
        return settings

    def ensure_default_settings(self, db: Session, tenant_id: UUID) -> TenantWhatsAppSettings:
        """Idempotent: ensure a settings row exists for tenant."""
        return self._get_or_create(db, tenant_id)


whatsapp_settings_service = WhatsAppSettingsService()
