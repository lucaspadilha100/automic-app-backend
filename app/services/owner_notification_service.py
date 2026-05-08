"""
Service to emit and read OwnerNotification rows.

The `emit_*` methods are the small, named entry points used by hooks
(post-tenant-create, support-ticket-create, etc). They never raise — owner
notifications are *advisory*, not core business logic, so a failure to insert
must not break the caller.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import uuid
import logging

from sqlalchemy.orm import Session

from app.models.owner_notification import (
    OwnerNotification, OwnerNotificationType, OwnerNotificationSeverity,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OwnerNotificationService:
    def emit(
        self,
        db: Session,
        notification_type: OwnerNotificationType,
        title: str,
        message: Optional[str] = None,
        severity: OwnerNotificationSeverity = OwnerNotificationSeverity.info,
        tenant_id: Optional[uuid.UUID] = None,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[uuid.UUID] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[OwnerNotification]:
        """Emit a notification. Always swallows errors to avoid breaking the caller."""
        try:
            note = OwnerNotification(
                notification_type=notification_type,
                severity=severity,
                title=title,
                message=message,
                tenant_id=tenant_id,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
                payload=payload,
                is_read=False,
            )
            db.add(note)
            db.flush()
            return note
        except Exception as exc:
            logger.warning("Failed to emit owner notification: %s", exc)
            try:
                db.rollback()
            except Exception:
                pass
            return None

    # ── Convenience emitters (hooks call these) ─────────────────────────────
    def emit_tenant_signup(self, db: Session, tenant_id: uuid.UUID, tenant_name: str):
        return self.emit(
            db,
            notification_type=OwnerNotificationType.tenant_signup,
            severity=OwnerNotificationSeverity.success,
            title=f"Novo tenant: {tenant_name}",
            message=f"Tenant '{tenant_name}' acabou de ser criado.",
            tenant_id=tenant_id,
            related_entity_type="tenant",
            related_entity_id=tenant_id,
        )

    def emit_tenant_status_change(
        self, db: Session, tenant_id: uuid.UUID, tenant_name: str,
        old_status: str, new_status: str,
    ):
        type_map = {
            "cancelled": (OwnerNotificationType.tenant_cancelled, OwnerNotificationSeverity.error),
            "suspended": (OwnerNotificationType.tenant_suspended, OwnerNotificationSeverity.warning),
            "active": (OwnerNotificationType.tenant_reactivated, OwnerNotificationSeverity.success),
        }
        notif_type, severity = type_map.get(
            new_status,
            (OwnerNotificationType.custom, OwnerNotificationSeverity.info),
        )
        return self.emit(
            db,
            notification_type=notif_type,
            severity=severity,
            title=f"Tenant {tenant_name}: {old_status} → {new_status}",
            tenant_id=tenant_id,
            related_entity_type="tenant",
            related_entity_id=tenant_id,
            payload={"old_status": old_status, "new_status": new_status},
        )

    def emit_support_ticket_created(
        self, db: Session, ticket_id: uuid.UUID, tenant_id: uuid.UUID,
        tenant_name: str, subject: str, priority: str,
    ):
        sev = (
            OwnerNotificationSeverity.error if priority == "urgent"
            else OwnerNotificationSeverity.warning if priority == "high"
            else OwnerNotificationSeverity.info
        )
        return self.emit(
            db,
            notification_type=OwnerNotificationType.support_ticket_created,
            severity=sev,
            title=f"Novo ticket de {tenant_name}",
            message=f"[{priority}] {subject}",
            tenant_id=tenant_id,
            related_entity_type="support_ticket",
            related_entity_id=ticket_id,
            payload={"priority": priority, "subject": subject},
        )

    def emit_support_ticket_replied(
        self, db: Session, ticket_id: uuid.UUID, tenant_id: uuid.UUID,
        tenant_name: str, subject: str,
    ):
        return self.emit(
            db,
            notification_type=OwnerNotificationType.support_ticket_replied,
            severity=OwnerNotificationSeverity.info,
            title=f"Resposta em ticket de {tenant_name}",
            message=subject,
            tenant_id=tenant_id,
            related_entity_type="support_ticket",
            related_entity_id=ticket_id,
        )

    # ── Read API ────────────────────────────────────────────────────────────
    def list(
        self,
        db: Session,
        unread_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[OwnerNotification]:
        q = db.query(OwnerNotification)
        if unread_only:
            q = q.filter(OwnerNotification.is_read.is_(False))
        return (
            q.order_by(OwnerNotification.created_at.desc())
            .offset(offset).limit(limit).all()
        )

    def count_unread(self, db: Session) -> int:
        return (
            db.query(OwnerNotification)
            .filter(OwnerNotification.is_read.is_(False))
            .count()
        )

    def count_total(self, db: Session) -> int:
        return db.query(OwnerNotification).count()

    def mark_read(
        self, db: Session, notification_id: uuid.UUID, is_read: bool = True,
    ) -> Optional[OwnerNotification]:
        note = (
            db.query(OwnerNotification)
            .filter(OwnerNotification.id == notification_id)
            .first()
        )
        if not note:
            return None
        note.is_read = is_read
        note.read_at = _utcnow() if is_read else None
        db.add(note)
        db.commit()
        db.refresh(note)
        return note

    def mark_all_read(self, db: Session) -> int:
        now = _utcnow()
        count = (
            db.query(OwnerNotification)
            .filter(OwnerNotification.is_read.is_(False))
            .update(
                {"is_read": True, "read_at": now}, synchronize_session=False,
            )
        )
        db.commit()
        return count


owner_notification_service = OwnerNotificationService()
