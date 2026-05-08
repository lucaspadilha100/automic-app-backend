from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid
from datetime import datetime, timezone

from db.session import get_db
from app.core.dependencies import (
    get_current_user, require_active_tenant, require_manager_or_above,
)
from app.core.exceptions import NotFoundError, ProfessionalNotFoundError
from app.models.user import User
from app.models.tenant import Tenant
from app.models.professional import Professional, ProfessionalAvailability
from app.models.service import ProfessionalService, Service
from app.models.schedule import BusinessHour, BlockedTime
from app.services.plan_limit_service import plan_limit_service
from app.services.audit_service import audit_service
from app.schemas.schemas import (
    ProfessionalCreate, ProfessionalUpdate, ProfessionalResponse,
    ProfessionalServiceLink, AvailabilityCreate,
    BusinessHourCreate, BusinessHourResponse,
    BlockedTimeCreate, BlockedTimeResponse,
)

router = APIRouter(prefix="/professionals", tags=["Profissionais"])


@router.post("", response_model=ProfessionalResponse)
def create_professional(
    payload: ProfessionalCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    plan_limit_service.check_professional_limit(db, tenant)
    prof = Professional(tenant_id=tenant.id, **payload.model_dump())
    db.add(prof)
    db.flush()
    audit_service.log(db, "professional_created", "professional", prof.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(prof)
    return prof


@router.get("", response_model=List[ProfessionalResponse])
def list_professionals(
    active_only: bool = True,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Professional).filter(
        Professional.tenant_id == tenant.id, Professional.deleted_at.is_(None)
    )
    if active_only:
        q = q.filter(Professional.is_active == True)
    return q.all()


@router.get("/{professional_id}", response_model=ProfessionalResponse)
def get_professional(
    professional_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prof = db.query(Professional).filter(
        Professional.id == professional_id,
        Professional.tenant_id == tenant.id,
        Professional.deleted_at.is_(None),
    ).first()
    if not prof:
        raise ProfessionalNotFoundError()
    return prof


@router.put("/{professional_id}", response_model=ProfessionalResponse)
def update_professional(
    professional_id: uuid.UUID,
    payload: ProfessionalUpdate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    prof = db.query(Professional).filter(
        Professional.id == professional_id,
        Professional.tenant_id == tenant.id,
        Professional.deleted_at.is_(None),
    ).first()
    if not prof:
        raise ProfessionalNotFoundError()
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(prof, k, v)
    audit_service.log(db, "professional_updated", "professional", prof.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(prof)
    return prof


@router.delete("/{professional_id}")
def delete_professional(
    professional_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    prof = db.query(Professional).filter(
        Professional.id == professional_id,
        Professional.tenant_id == tenant.id,
        Professional.deleted_at.is_(None),
    ).first()
    if not prof:
        raise ProfessionalNotFoundError()
    prof.deleted_at = datetime.now(timezone.utc)
    prof.is_active = False
    audit_service.log(db, "professional_deleted", "professional", prof.id, tenant.id, current_user.id)
    db.commit()
    return {"message": "Profissional removido."}


# ---- Services link ----

@router.put("/{professional_id}/services")
def set_professional_services(
    professional_id: uuid.UUID,
    payload: ProfessionalServiceLink,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    prof = db.query(Professional).filter(
        Professional.id == professional_id, Professional.tenant_id == tenant.id
    ).first()
    if not prof:
        raise ProfessionalNotFoundError()

    # Validate all service IDs belong to tenant
    svcs = db.query(Service).filter(
        Service.id.in_(payload.service_ids),
        Service.tenant_id == tenant.id,
        Service.deleted_at.is_(None),
    ).all()
    if len(svcs) != len(payload.service_ids):
        raise NotFoundError("SERVICE_NOT_FOUND", "Um ou mais serviços não encontrados.")

    # Replace all links
    db.query(ProfessionalService).filter(
        ProfessionalService.professional_id == professional_id,
        ProfessionalService.tenant_id == tenant.id,
    ).delete()

    for svc in svcs:
        link = ProfessionalService(
            tenant_id=tenant.id,
            professional_id=professional_id,
            service_id=svc.id,
            created_at=datetime.now(timezone.utc),
        )
        db.add(link)

    audit_service.log(db, "professional_services_updated", "professional", prof.id, tenant.id, current_user.id)
    db.commit()
    return {"message": "Serviços vinculados atualizados.", "service_ids": [str(s.id) for s in svcs]}


@router.get("/{professional_id}/services")
def get_professional_services(
    professional_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    links = db.query(ProfessionalService).filter(
        ProfessionalService.professional_id == professional_id,
        ProfessionalService.tenant_id == tenant.id,
    ).all()
    return {"service_ids": [str(lk.service_id) for lk in links]}


# ---- Availability (weekly schedule) ----

@router.put("/{professional_id}/availability")
def set_availability(
    professional_id: uuid.UUID,
    payload: List[AvailabilityCreate],
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    prof = db.query(Professional).filter(
        Professional.id == professional_id, Professional.tenant_id == tenant.id
    ).first()
    if not prof:
        raise ProfessionalNotFoundError()

    db.query(ProfessionalAvailability).filter(
        ProfessionalAvailability.professional_id == professional_id,
        ProfessionalAvailability.tenant_id == tenant.id,
    ).delete()

    from datetime import time as t_type
    for slot in payload:
        def parse_time(s: Optional[str]):
            if not s:
                return None
            h, m = s.split(":")
            return t_type(int(h), int(m))

        pa = ProfessionalAvailability(
            tenant_id=tenant.id,
            professional_id=professional_id,
            weekday=slot.weekday,
            start_time=parse_time(slot.start_time),
            end_time=parse_time(slot.end_time),
            break_start_time=parse_time(slot.break_start_time),
            break_end_time=parse_time(slot.break_end_time),
            is_available=slot.is_available,
        )
        db.add(pa)

    db.commit()
    return {"message": "Disponibilidade atualizada."}


@router.get("/{professional_id}/availability")
def get_availability(
    professional_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(ProfessionalAvailability).filter(
        ProfessionalAvailability.professional_id == professional_id,
        ProfessionalAvailability.tenant_id == tenant.id,
    ).order_by(ProfessionalAvailability.weekday).all()
    return rows

