from typing import List
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import get_current_customer, get_public_tenant_by_slug
from app.models.customer import CustomerAccount
from app.models.tenant import Tenant
from app.schemas.term import TenantTermResponse, CustomerTermAcceptResponse
from app.services.term_service import term_service

router = APIRouter(prefix="/customer", tags=["Termos e Consentimentos - Portal do Cliente"])


@router.get("/tenants/{slug}/terms", response_model=List[TenantTermResponse])
def list_active_terms(
    slug: str,
    db: Session = Depends(get_db),
    current_customer: CustomerAccount = Depends(get_current_customer),
):
    tenant: Tenant = get_public_tenant_by_slug(slug, db)
    return term_service.list_active_terms_for_customer(db=db, tenant_id=tenant.id)


@router.post("/tenants/{slug}/terms/{term_id}/accept", response_model=CustomerTermAcceptResponse, status_code=201)
def accept_term(
    slug: str,
    term_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_customer: CustomerAccount = Depends(get_current_customer),
):
    import uuid
    tenant: Tenant = get_public_tenant_by_slug(slug, db)
    acceptance = term_service.accept_term(
        db=db,
        tenant_id=tenant.id,
        term_id=uuid.UUID(term_id),
        customer_account_id=current_customer.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return CustomerTermAcceptResponse(
        accepted=True,
        acceptance_id=acceptance.id,
        term_id=acceptance.term_id,
        term_type=acceptance.term.term_type,
        version=acceptance.term.version,
        accepted_at=acceptance.accepted_at,
    )
