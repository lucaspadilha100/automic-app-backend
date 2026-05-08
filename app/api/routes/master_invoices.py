"""
Master billing routes — manage tenant invoices and run billing enforcement jobs.
"""
import uuid
from typing import List, Optional
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import require_super_admin
from app.models.user import User
from app.models.tenant_invoice import InvoiceStatus
from app.schemas.tenant_invoice import (
    InvoiceResponse, InvoicePaidUpdate, InvoiceCancelUpdate,
    InvoiceChargeRequest, InvoiceChargeResponse,
    GenerateInvoicesResponse, MarkOverdueResponse, BillingEnforcementResponse,
)
from app.services.invoice_service import invoice_service
from app.services.task_run_service import task_run_service
from app.models.task_run import TaskRunSource

router = APIRouter(prefix="/master/invoices", tags=["Faturas dos Tenants - Master"])
jobs_router = APIRouter(prefix="/master/jobs", tags=["Jobs - Master"])


@router.get("", response_model=List[InvoiceResponse])
def list_invoices(
    tenant_id: Optional[str] = Query(None),
    status: Optional[InvoiceStatus] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return invoice_service.list_invoices(
        db,
        tenant_id=uuid.UUID(tenant_id) if tenant_id else None,
        status=status, limit=limit, offset=offset,
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: str,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return invoice_service.get_invoice(db, uuid.UUID(invoice_id))


@router.post("/{invoice_id}/charge", response_model=InvoiceChargeResponse)
def create_charge(
    invoice_id: str,
    payload: InvoiceChargeRequest,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return invoice_service.create_charge(db, uuid.UUID(invoice_id), payload.method)


@router.post("/{invoice_id}/mark-paid", response_model=InvoiceResponse)
def mark_paid(
    invoice_id: str,
    payload: InvoicePaidUpdate,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return invoice_service.mark_paid(
        db, uuid.UUID(invoice_id),
        payment_method=payload.payment_method,
        payment_provider=payload.payment_provider,
        payment_reference=payload.payment_reference,
        notes=payload.notes,
    )


@router.post("/{invoice_id}/cancel", response_model=InvoiceResponse)
def cancel_invoice(
    invoice_id: str,
    payload: InvoiceCancelUpdate,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return invoice_service.cancel_invoice(db, uuid.UUID(invoice_id), payload.reason)


# ── Jobs ──────────────────────────────────────────────────────────────────────

@jobs_router.post("/generate-monthly-invoices", response_model=GenerateInvoicesResponse)
def generate_monthly_invoices(
    period_start: Optional[date] = Query(None),
    period_end: Optional[date] = Query(None),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Idempotent — re-running for the same period skips already-issued invoices."""
    with task_run_service.record(db, "generate_monthly_invoices", TaskRunSource.manual) as ctx:
        result = invoice_service.generate_monthly_invoices(db, period_start, period_end)
        ctx.set_summary(result)
        return result


@jobs_router.post("/mark-overdue-invoices", response_model=MarkOverdueResponse)
def mark_overdue_invoices(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    with task_run_service.record(db, "mark_overdue_invoices", TaskRunSource.manual) as ctx:
        result = invoice_service.mark_overdue(db)
        ctx.set_summary(result)
        return result


@jobs_router.post("/enforce-billing", response_model=BillingEnforcementResponse)
def enforce_billing(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Apply suspension/cancellation/reactivation rules based on overdue invoices."""
    with task_run_service.record(db, "enforce_billing", TaskRunSource.manual) as ctx:
        result = invoice_service.enforce_billing(db)
        ctx.set_summary(result)
        return result
