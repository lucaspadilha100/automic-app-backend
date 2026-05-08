import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import require_active_tenant, require_manager_or_above
from app.models.user import User
from app.models.tenant import Tenant
from app.models.automation import ActionType
from app.schemas.automation import (
    AutomationRuleCreate, AutomationRuleUpdate, AutomationRuleStatusUpdate,
    AutomationRuleResponse,
)
from app.services.automation_service import automation_service

router = APIRouter(prefix="/admin/automations", tags=["Automation Rules"])


@router.get("", response_model=List[AutomationRuleResponse])
def list_rules(
    trigger_event: Optional[str] = Query(None),
    action_type: Optional[ActionType] = Query(None),
    is_active: Optional[bool] = Query(None),
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return automation_service.list_rules(
        db=db, tenant=tenant,
        trigger_event=trigger_event, action_type=action_type, is_active=is_active,
    )


@router.post("", response_model=AutomationRuleResponse, status_code=201)
def create_rule(
    payload: AutomationRuleCreate,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return automation_service.create_rule(
        db=db, tenant=tenant, data=payload.model_dump(),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.get("/{automation_id}", response_model=AutomationRuleResponse)
def get_rule(
    automation_id: str,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return automation_service.get_rule(db=db, tenant=tenant, rule_id=uuid.UUID(automation_id))


@router.put("/{automation_id}", response_model=AutomationRuleResponse)
def update_rule(
    automation_id: str,
    payload: AutomationRuleUpdate,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return automation_service.update_rule(
        db=db, tenant=tenant, rule_id=uuid.UUID(automation_id),
        data=payload.model_dump(exclude_none=True),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.patch("/{automation_id}/status", response_model=AutomationRuleResponse)
def set_rule_status(
    automation_id: str,
    payload: AutomationRuleStatusUpdate,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return automation_service.set_rule_status(
        db=db, tenant=tenant, rule_id=uuid.UUID(automation_id),
        is_active=payload.is_active,
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.delete("/{automation_id}", status_code=204)
def delete_rule(
    automation_id: str,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    automation_service.delete_or_disable_rule(
        db=db, tenant=tenant, rule_id=uuid.UUID(automation_id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
