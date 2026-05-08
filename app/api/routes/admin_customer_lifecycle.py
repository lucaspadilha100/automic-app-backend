import uuid
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import require_active_tenant, require_manager_or_above
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.customer_lifecycle import (
    CustomerLifecycleResponse, CustomerLifecycleSummaryResponse,
    CustomerLifecycleCustomerListItem, CustomerLifecycleRecalculateResponse,
    TenantLifecycleSettingsResponse, TenantLifecycleSettingsUpdate,
)
from app.services.customer_lifecycle_service import customer_lifecycle_service

router = APIRouter(prefix="/admin/customer-lifecycle", tags=["Customer Lifecycle"])
customers_router = APIRouter(prefix="/admin/customers", tags=["Customer Lifecycle"])


# ── Settings ──────────────────────────────────────────────────────────────────

@router.get("/settings", response_model=TenantLifecycleSettingsResponse)
def get_lifecycle_settings(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return customer_lifecycle_service.get_settings(db=db, tenant=tenant)


@router.put("/settings", response_model=TenantLifecycleSettingsResponse)
def update_lifecycle_settings(
    payload: TenantLifecycleSettingsUpdate,
    request: Request,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return customer_lifecycle_service.update_settings(
        db=db, tenant=tenant,
        data=payload.model_dump(exclude_none=True),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


# ── Summary & list ────────────────────────────────────────────────────────────

@router.get("/summary", response_model=CustomerLifecycleSummaryResponse)
def get_lifecycle_summary(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return customer_lifecycle_service.get_summary(db=db, tenant=tenant)


@router.get("/customers", response_model=List[CustomerLifecycleCustomerListItem])
def list_lifecycle_customers(
    lifecycle_status: Optional[str] = Query(None),
    min_total_spent: Optional[Decimal] = Query(None),
    max_total_spent: Optional[Decimal] = Query(None),
    has_next_appointment: Optional[bool] = Query(None),
    no_show_count_min: Optional[int] = Query(None),
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    rows = customer_lifecycle_service.list_customers(
        db=db, tenant=tenant,
        lifecycle_status=lifecycle_status,
        min_total_spent=min_total_spent,
        max_total_spent=max_total_spent,
        has_next_appointment=has_next_appointment,
        no_show_count_min=no_show_count_min,
    )
    # TenantCustomer's primary key is `id`; the response schema names it
    # `tenant_customer_id` for clarity. Map explicitly.
    return [
        CustomerLifecycleCustomerListItem(
            tenant_customer_id=tc.id,
            customer_account_id=tc.customer_account_id,
            lifecycle_status=tc.lifecycle_status,
            last_appointment_at=tc.last_appointment_at,
            next_appointment_at=tc.next_appointment_at,
            total_spent=Decimal(str(tc.total_spent or 0)),
            appointments_count=tc.appointments_count or 0,
            no_show_count=tc.no_show_count or 0,
        )
        for tc in rows
    ]


# ── Recalculate all ───────────────────────────────────────────────────────────

@router.post("/recalculate-all")
def recalculate_all(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    changed = customer_lifecycle_service.recalculate_all(db=db, tenant=tenant, user_id=current_user.id)
    return {"recalculated": True, "customers_changed": changed}


# ── Per-customer ──────────────────────────────────────────────────────────────

@customers_router.get("/{tenant_customer_id}/lifecycle", response_model=CustomerLifecycleResponse)
def get_customer_lifecycle(
    tenant_customer_id: str,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    tc = customer_lifecycle_service.get_customer_lifecycle(
        db=db, tenant=tenant, tenant_customer_id=uuid.UUID(tenant_customer_id)
    )
    return CustomerLifecycleResponse(
        tenant_customer_id=tc.id,
        customer_account_id=tc.customer_account_id,
        lifecycle_status=tc.lifecycle_status,
        last_appointment_at=tc.last_appointment_at,
        next_appointment_at=tc.next_appointment_at,
        total_spent=Decimal(str(tc.total_spent or 0)),
        appointments_count=tc.appointments_count or 0,
        no_show_count=tc.no_show_count or 0,
        updated_at=tc.updated_at,
    )


@customers_router.post("/{tenant_customer_id}/lifecycle/recalculate",
                       response_model=CustomerLifecycleRecalculateResponse)
def recalculate_customer_lifecycle(
    tenant_customer_id: str,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    result = customer_lifecycle_service.recalculate_customer(
        db=db, tenant=tenant,
        tenant_customer_id=uuid.UUID(tenant_customer_id),
        user_id=current_user.id,
    )
    return CustomerLifecycleRecalculateResponse(**result)
