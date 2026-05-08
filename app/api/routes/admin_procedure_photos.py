import uuid
from typing import List
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import require_active_tenant, require_manager_or_above, require_feature
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.procedure_photo import (
    ProcedurePhotoCreate, ProcedurePhotoUpdate, ProcedurePhotoResponse,
)
from app.services.procedure_photo_service import procedure_photo_service

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
