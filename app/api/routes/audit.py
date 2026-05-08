from typing import Optional
from datetime import date, datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import uuid

from db.session import get_db
from app.core.dependencies import require_active_tenant, require_manager_or_above
from app.models.user import User
from app.models.tenant import Tenant
from app.models.audit import AuditLog

router = APIRouter(prefix="/audit-logs", tags=["Auditoria"])


@router.get("")
def list_audit_logs(
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    skip: int = 0,
    limit: int = Query(50, le=200),
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog).filter(AuditLog.tenant_id == tenant.id)

    if action:
        q = q.filter(AuditLog.action.ilike(f"%{action}%"))
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        q = q.filter(AuditLog.entity_id == entity_id)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if date_from:
        q = q.filter(AuditLog.created_at >= datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc))
    if date_to:
        dt_to = datetime(date_to.year, date_to.month, date_to.day, tzinfo=timezone.utc) + timedelta(days=1)
        q = q.filter(AuditLog.created_at < dt_to)

    total = q.count()
    rows = q.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "items": [
            {
                "id": str(r.id),
                "action": r.action,
                "entity_type": r.entity_type,
                "entity_id": str(r.entity_id) if r.entity_id else None,
                "user_id": str(r.user_id) if r.user_id else None,
                "old_values": r.old_values,
                "new_values": r.new_values,
                "ip_address": r.ip_address,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


@router.get("/actions")
def list_audit_actions(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    """Lista todos os tipos de ação distintos registrados."""
    from sqlalchemy import distinct
    actions = db.query(distinct(AuditLog.action)).filter(
        AuditLog.tenant_id == tenant.id
    ).all()
    return [a[0] for a in actions]
