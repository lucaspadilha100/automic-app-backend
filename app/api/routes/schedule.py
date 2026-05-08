"""
Rotas de horários de funcionamento e bloqueios.
Separadas do router de professionals para evitar conflito com /{professional_id}.

Endpoints:
  GET/PUT  /schedule/business-hours
  GET/POST/DELETE /schedule/blocked-times
"""
from typing import List, Optional
from datetime import datetime, timezone, time as time_type
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid

from db.session import get_db
from app.core.dependencies import (
    get_current_user, require_active_tenant, require_manager_or_above,
)
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.models.tenant import Tenant
from app.models.schedule import BusinessHour, BlockedTime
from app.services.audit_service import audit_service
from app.schemas.schemas import (
    BusinessHourCreate, BusinessHourResponse,
    BlockedTimeCreate, BlockedTimeResponse,
)

router = APIRouter(prefix="/schedule", tags=["Horários de Funcionamento"])


def _parse_time(s: Optional[str]) -> Optional[time_type]:
    if not s:
        return None
    parts = s.split(":")
    return time_type(int(parts[0]), int(parts[1]))


# ── Business Hours ─────────────────────────────────────────────────────────────

@router.put("/business-hours")
def set_business_hours(
    payload: List[BusinessHourCreate],
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    """Define os horários de funcionamento da empresa (substitui todos os existentes)."""
    db.query(BusinessHour).filter(BusinessHour.tenant_id == tenant.id).delete()

    for bh in payload:
        row = BusinessHour(
            tenant_id=tenant.id,
            unit_id=bh.unit_id,
            weekday=bh.weekday,
            open_time=_parse_time(bh.open_time),
            close_time=_parse_time(bh.close_time),
            break_start_time=_parse_time(bh.break_start_time),
            break_end_time=_parse_time(bh.break_end_time),
            is_closed=bh.is_closed,
        )
        db.add(row)

    audit_service.log(db, "business_hours_updated", "tenant", tenant.id, tenant.id, current_user.id)
    db.commit()
    return {"message": "Horários de funcionamento atualizados."}


@router.get("/business-hours", response_model=List[BusinessHourResponse])
def get_business_hours(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(BusinessHour)
        .filter(BusinessHour.tenant_id == tenant.id)
        .order_by(BusinessHour.weekday)
        .all()
    )


# ── Blocked Times ──────────────────────────────────────────────────────────────

@router.post("/blocked-times", response_model=BlockedTimeResponse)
def create_blocked_time(
    payload: BlockedTimeCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    bt = BlockedTime(
        tenant_id=tenant.id,
        created_by_user_id=current_user.id,
        **payload.model_dump(),
    )
    db.add(bt)
    db.commit()
    db.refresh(bt)
    return bt


@router.get("/blocked-times", response_model=List[BlockedTimeResponse])
def list_blocked_times(
    professional_id: Optional[uuid.UUID] = None,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(BlockedTime).filter(BlockedTime.tenant_id == tenant.id)
    if professional_id:
        q = q.filter(BlockedTime.professional_id == professional_id)
    return q.order_by(BlockedTime.start_datetime).all()


@router.delete("/blocked-times/{blocked_time_id}")
def delete_blocked_time(
    blocked_time_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    bt = db.query(BlockedTime).filter(
        BlockedTime.id == blocked_time_id, BlockedTime.tenant_id == tenant.id
    ).first()
    if not bt:
        raise NotFoundError("BLOCKED_TIME_NOT_FOUND", "Bloqueio não encontrado.")
    db.delete(bt)
    db.commit()
    return {"message": "Bloqueio removido."}
