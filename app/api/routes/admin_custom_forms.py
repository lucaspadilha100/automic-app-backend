import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import require_active_tenant, require_manager_or_above
from app.models.user import User
from app.models.tenant import Tenant
from app.models.custom_form import FormType
from app.schemas.custom_form import (
    CustomFormCreate, CustomFormUpdate, CustomFormStatusUpdate,
    CustomFormResponse, CustomFormWithFieldsResponse,
    CustomFormFieldCreate, CustomFormFieldUpdate, CustomFormFieldResponse,
    CustomFormResponseResponse,
)
from app.services.custom_form_service import custom_form_service

router = APIRouter(prefix="/admin/forms", tags=["Formulários Personalizados - Administrativo"])


# ── Forms ─────────────────────────────────────────────────────────────────────

@router.get("", response_model=List[CustomFormResponse])
def list_forms(
    form_type: Optional[FormType] = Query(None),
    is_active: Optional[bool] = Query(None),
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return custom_form_service.list_forms(db=db, tenant=tenant, form_type=form_type, is_active=is_active)


@router.post("", response_model=CustomFormWithFieldsResponse, status_code=201)
def create_form(
    payload: CustomFormCreate,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return custom_form_service.create_form(
        db=db, tenant=tenant, data=payload.model_dump(),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.get("/responses/{response_id}", response_model=CustomFormResponseResponse)
def get_response(
    response_id: str,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return custom_form_service.get_response(db=db, tenant=tenant, response_id=uuid.UUID(response_id))


@router.get("/{form_id}", response_model=CustomFormWithFieldsResponse)
def get_form(
    form_id: str,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return custom_form_service.get_form(db=db, tenant=tenant, form_id=uuid.UUID(form_id))


@router.put("/{form_id}", response_model=CustomFormWithFieldsResponse)
def update_form(
    form_id: str,
    payload: CustomFormUpdate,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return custom_form_service.update_form(
        db=db, tenant=tenant, form_id=uuid.UUID(form_id),
        data=payload.model_dump(exclude_none=True),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.patch("/{form_id}/status", response_model=CustomFormResponse)
def set_form_status(
    form_id: str,
    payload: CustomFormStatusUpdate,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return custom_form_service.set_form_status(
        db=db, tenant=tenant, form_id=uuid.UUID(form_id), is_active=payload.is_active,
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


# ── Fields ────────────────────────────────────────────────────────────────────

@router.post("/{form_id}/fields", response_model=CustomFormFieldResponse, status_code=201)
def add_field(
    form_id: str,
    payload: CustomFormFieldCreate,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return custom_form_service.add_field(
        db=db, tenant=tenant, form_id=uuid.UUID(form_id),
        data=payload.model_dump(),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.put("/{form_id}/fields/{field_id}", response_model=CustomFormFieldResponse)
def update_field(
    form_id: str,
    field_id: str,
    payload: CustomFormFieldUpdate,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return custom_form_service.update_field(
        db=db, tenant=tenant, form_id=uuid.UUID(form_id), field_id=uuid.UUID(field_id),
        data=payload.model_dump(exclude_none=True),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.delete("/{form_id}/fields/{field_id}", status_code=204)
def delete_field(
    form_id: str,
    field_id: str,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    custom_form_service.delete_field(
        db=db, tenant=tenant, form_id=uuid.UUID(form_id), field_id=uuid.UUID(field_id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


# ── Responses ─────────────────────────────────────────────────────────────────

@router.get("/{form_id}/responses", response_model=List[CustomFormResponseResponse])
def list_responses(
    form_id: str,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return custom_form_service.list_responses(db=db, tenant=tenant, form_id=uuid.UUID(form_id))
