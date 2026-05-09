import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from db.session import get_db
from app.core.dependencies import require_active_tenant, require_manager_or_above, require_feature
from app.models.user import User
from app.models.tenant import Tenant
from app.models.procedure import ProcedureHistory
from app.schemas.procedure_photo import (
    ProcedurePhotoCreate, ProcedurePhotoUpdate, ProcedurePhotoResponse,
)
from app.services.procedure_photo_service import procedure_photo_service


class ProcedureHistoryResponse(BaseModel):
    id: uuid.UUID
    tenant_customer_id: uuid.UUID
    customer_account_id: Optional[uuid.UUID]
    appointment_id: Optional[uuid.UUID]
    professional_id: Optional[uuid.UUID]
    service_id: Optional[uuid.UUID]
    title: str
    description: Optional[str]
    procedure_date: datetime
    public_notes: Optional[str]
    photo_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


history_router = APIRouter(
    prefix="/admin/procedure-history",
    tags=["Fotos de Procedimento - Administrativo"],
    dependencies=[Depends(require_feature("before_after_photos"))],
)


@history_router.get("", response_model=List[ProcedureHistoryResponse])
def list_procedure_histories(
    tenant_customer_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(50, le=200),
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    q = db.query(ProcedureHistory).filter(ProcedureHistory.tenant_id == tenant.id)
    if tenant_customer_id:
        q = q.filter(ProcedureHistory.tenant_customer_id == tenant_customer_id)
    rows = q.order_by(ProcedureHistory.procedure_date.desc()).limit(limit).all()
    result = []
    for ph in rows:
        d = ProcedureHistoryResponse.model_validate(ph)
        d.photo_count = len(ph.photos)
        result.append(d)
    return result


router = APIRouter(
    prefix="/admin/procedure-history/{procedure_id}/photos",
    tags=["Fotos de Procedimento - Administrativo"],
    dependencies=[Depends(require_feature("before_after_photos"))],
)


@router.get("", response_model=List[ProcedurePhotoResponse])
def list_photos(
    procedure_id: str,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return procedure_photo_service.list_photos_for_procedure(
        db=db,
        tenant_id=tenant.id,
        procedure_id=uuid.UUID(procedure_id),
    )


@router.post("", response_model=ProcedurePhotoResponse, status_code=201)
def add_photo(
    procedure_id: str,
    payload: ProcedurePhotoCreate,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return procedure_photo_service.add_photo(
        db=db,
        tenant_id=tenant.id,
        procedure_id=uuid.UUID(procedure_id),
        data=payload.model_dump(),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.get("/{photo_id}", response_model=ProcedurePhotoResponse)
def get_photo(
    procedure_id: str,
    photo_id: str,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return procedure_photo_service.get_photo(
        db=db,
        tenant_id=tenant.id,
        procedure_id=uuid.UUID(procedure_id),
        photo_id=uuid.UUID(photo_id),
    )


@router.put("/{photo_id}", response_model=ProcedurePhotoResponse)
def update_photo(
    procedure_id: str,
    photo_id: str,
    payload: ProcedurePhotoUpdate,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return procedure_photo_service.update_photo(
        db=db,
        tenant_id=tenant.id,
        procedure_id=uuid.UUID(procedure_id),
        photo_id=uuid.UUID(photo_id),
        data=payload.model_dump(exclude_none=True),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.delete("/{photo_id}", status_code=204)
def remove_photo(
    procedure_id: str,
    photo_id: str,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    procedure_photo_service.remove_photo(
        db=db,
        tenant_id=tenant.id,
        procedure_id=uuid.UUID(procedure_id),
        photo_id=uuid.UUID(photo_id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
