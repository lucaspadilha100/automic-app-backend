from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import uuid

from db.session import get_db
from app.core.dependencies import (
    get_current_user, require_active_tenant, get_public_tenant_by_slug,
)
from app.models.user import User
from app.models.tenant import Tenant
from app.services.availability_service import availability_service

router = APIRouter(tags=["Disponibilidade"])


# ---- Admin panel availability ----

@router.get("/availability/slots")
def get_slots_admin(
    service_ids: List[uuid.UUID] = Query(...),
    target_date: date = Query(...),
    professional_id: Optional[uuid.UUID] = Query(None),
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Consultar slots disponíveis pelo painel administrativo."""
    return availability_service.get_available_slots(
        db=db,
        tenant=tenant,
        service_ids=service_ids,
        target_date=target_date,
        professional_id=professional_id,
        any_professional=professional_id is None,
    )


# ---- Public booking page availability ----

@router.get("/public/{slug}/availability")
def get_slots_public(
    slug: str,
    service_ids: List[uuid.UUID] = Query(...),
    target_date: date = Query(...),
    professional_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
):
    """Consultar slots disponíveis na página pública de agendamento."""
    tenant = get_public_tenant_by_slug(slug, db)
    return availability_service.get_available_slots(
        db=db,
        tenant=tenant,
        service_ids=service_ids,
        target_date=target_date,
        professional_id=professional_id,
        any_professional=professional_id is None,
    )
