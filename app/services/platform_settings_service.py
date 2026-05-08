"""
Service layer for the singleton `PlatformSettings`.

Ensures exactly one row exists (lazily creating it with sensible defaults
on first read) and centralizes the audit / mutation logic.
"""
from typing import Optional, Dict, Any
import uuid

from sqlalchemy.orm import Session

from app.models.platform_settings import PlatformSettings
from app.services.audit_service import audit_service


class PlatformSettingsService:
    def get_or_create(self, db: Session) -> PlatformSettings:
        """Return the singleton row, creating it with defaults if it does not exist."""
        row = db.query(PlatformSettings).first()
        if row is None:
            row = PlatformSettings(is_singleton=True)
            db.add(row)
            db.commit()
            db.refresh(row)
        return row

    def update(
        self,
        db: Session,
        data: Dict[str, Any],
        user_id: Optional[uuid.UUID],
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> PlatformSettings:
        row = self.get_or_create(db)
        # Capture before-state for audit
        before = {k: getattr(row, k) for k in data.keys()}
        for k, v in data.items():
            setattr(row, k, v)
        db.add(row)
        db.commit()
        db.refresh(row)

        # Audit at the platform scope (no tenant_id — this is a global config).
        try:
            audit_service.log(
                db=db,
                tenant_id=None,
                user_id=user_id,
                action="platform_settings.update",
                entity_type="platform_settings",
                entity_id=row.id,
                old_values=_serialize(before),
                new_values=_serialize(data),
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except Exception:
            # Never fail platform settings update because audit logging hiccupped.
            pass
        return row


def _serialize(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: (str(v) if v is not None else None) for k, v in d.items()}


platform_settings_service = PlatformSettingsService()
