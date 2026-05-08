import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import require_active_tenant, require_manager_or_above, require_feature
from app.models.user import User
from app.models.tenant import Tenant
from app.models.commission import CommissionStatus
from app.schemas.commission import (
    CommissionSettingCreate, CommissionSettingUpdate, CommissionSettingStatusUpdate,
    CommissionSettingResponse, CommissionRecordResponse,
)
from app.services.commission_service import commission_service

router = APIRouter(
    prefix="/admin/commissions",
    tags=["Comissões de Profissionais"],
    dependencies=[Depends(require_feature("commissions"))],
)


# ── Settings ──────────────────────────────────────────────────────────────────

@router.get("/settings", response_model=List[CommissionSettingResponse])
def list_settings(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return commission_service.list_settings(db=db, tenant_id=tenant.id)


@router.post("/settings", response_model=CommissionSettingResponse, status_code=201)
def create_setting(
    payload: CommissionSettingCreate,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return commission_service.create_setting(
        db=db,
        tenant_id=tenant.id,
        data=payload.model_dump(),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.get("/settings/{setting_id}", response_model=CommissionSettingResponse)
def get_setting(
    setting_id: str,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return commission_service.get_setting(db=db, tenant_id=tenant.id, setting_id=uuid.UUID(setting_id))


@router.put("/settings/{setting_id}", response_model=CommissionSettingResponse)
def update_setting(
    setting_id: str,
    payload: CommissionSettingUpdate,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return commission_service.update_setting(
        db=db,
        tenant_id=tenant.id,
        setting_id=uuid.UUID(setting_id),
        data=payload.model_dump(exclude_none=True),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.patch("/settings/{setting_id}/status", response_model=CommissionSettingResponse)
def set_setting_status(
    setting_id: str,
    payload: CommissionSettingStatusUpdate,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return commission_service.set_setting_status(
        db=db,
        tenant_id=tenant.id,
        setting_id=uuid.UUID(setting_id),
        is_active=payload.is_active,
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


# ── Records ───────────────────────────────────────────────────────────────────

@router.get("/records", response_model=List[CommissionRecordResponse])
def list_records(
    professional_id: Optional[str] = Query(None),
    status: Optional[CommissionStatus] = Query(None),
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    prof_id = uuid.UUID(professional_id) if professional_id else None
    return commission_service.list_records(
        db=db, tenant_id=tenant.id, professional_id=prof_id, status=status
    )


@router.get("/records/{record_id}", response_model=CommissionRecordResponse)
def get_record(
    record_id: str,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return commission_service.get_record(db=db, tenant_id=tenant.id, record_id=uuid.UUID(record_id))


@router.post("/records/{record_id}/mark-paid", response_model=CommissionRecordResponse)
def mark_paid(
    record_id: str,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return commission_service.mark_paid(
        db=db,
        tenant_id=tenant.id,
        record_id=uuid.UUID(record_id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/records/{record_id}/cancel", response_model=CommissionRecordResponse)
def cancel_record(
    record_id: str,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return commission_service.cancel_record(
        db=db,
        tenant_id=tenant.id,
        record_id=uuid.UUID(record_id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
