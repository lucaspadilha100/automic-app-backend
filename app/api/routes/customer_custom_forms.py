import uuid
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import get_current_customer, get_public_tenant_by_slug
from app.models.customer import CustomerAccount
from app.schemas.custom_form import (
    CustomFormResponse, CustomFormWithFieldsResponse,
    CustomFormSubmit, CustomFormResponseResponse,
)
from app.services.custom_form_service import custom_form_service

router = APIRouter(prefix="/customer", tags=["Formulários Personalizados - Portal do Cliente"])


@router.get("/tenants/{slug}/forms", response_model=List[CustomFormResponse])
def list_active_forms(
    slug: str,
    db: Session = Depends(get_db),
    current_customer: CustomerAccount = Depends(get_current_customer),
):
    tenant = get_public_tenant_by_slug(slug, db)
    return custom_form_service.list_active_forms_for_customer(db=db, tenant=tenant)


@router.get("/tenants/{slug}/forms/{form_id}", response_model=CustomFormWithFieldsResponse)
def get_active_form(
    slug: str,
    form_id: str,
    db: Session = Depends(get_db),
    current_customer: CustomerAccount = Depends(get_current_customer),
):
    tenant = get_public_tenant_by_slug(slug, db)
    return custom_form_service.get_active_form_for_customer(db=db, tenant=tenant, form_id=uuid.UUID(form_id))


@router.post("/tenants/{slug}/forms/{form_id}/submit", response_model=CustomFormResponseResponse, status_code=201)
def submit_form(
    slug: str,
    form_id: str,
    payload: CustomFormSubmit,
    db: Session = Depends(get_db),
    current_customer: CustomerAccount = Depends(get_current_customer),
):
    tenant = get_public_tenant_by_slug(slug, db)
    return custom_form_service.submit_response(
        db=db,
        tenant=tenant,
        form_id=uuid.UUID(form_id),
        customer_account_id=current_customer.id,
        answers=payload.answers,
        appointment_id=payload.appointment_id,
    )
