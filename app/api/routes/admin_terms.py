from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import require_active_tenant, require_manager_or_above, require_feature
from app.models.user import User
from app.models.tenant import Tenant
from app.models.term import TermType
from app.schemas.term import (
    TenantTermCreate, TenantTermUpdate, TenantTermStatusUpdate, TenantTermResponse
)
from app.services.term_service import term_service

router = APIRouter(
    prefix="/admin/terms",
    tags=["Termos e Consentimentos - Administrativo"],
    dependencies=[Depends(require_feature("custom_terms"))],
)


@router.get("", response_model=List[TenantTermResponse])
def list_terms(
    term_type: Optional[TermType] = Query(None),
    is_active: Optional[bool] = Query(None),
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return term_service.list_terms(
        db=db,
        tenant_id=tenant.id,
        term_type=term_type,
        is_active=is_active,
    )


@router.post("", response_model=TenantTermResponse, status_code=201)
def create_term(
    payload: TenantTermCreate,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return term_service.create_term(
        db=db,
        tenant_id=tenant.id,
        data=payload.model_dump(),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.get("/{term_id}", response_model=TenantTermResponse)
def get_term(
    term_id: str,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    import uuid
    return term_service.get_term(db=db, tenant_id=tenant.id, term_id=uuid.UUID(term_id))


@router.put("/{term_id}", response_model=TenantTermResponse)
def update_term(
    term_id: str,
    payload: TenantTermUpdate,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    import uuid
    return term_service.update_term(
        db=db,
        tenant_id=tenant.id,
        term_id=uuid.UUID(term_id),
        data=payload.model_dump(exclude_none=True),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.patch("/{term_id}/status", response_model=TenantTermResponse)
def set_term_status(
    term_id: str,
    payload: TenantTermStatusUpdate,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    import uuid
    return term_service.set_term_status(
        db=db,
        tenant_id=tenant.id,
        term_id=uuid.UUID(term_id),
        is_active=payload.is_active,
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
