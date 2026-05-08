import uuid
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.dependencies import get_current_customer, get_public_tenant_by_slug
from app.models.customer import CustomerAccount
from app.models.tenant import Tenant
from app.schemas.procedure_photo import ProcedurePhotoCustomerResponse
from app.services.procedure_photo_service import procedure_photo_service

router = APIRouter(prefix="/customer", tags=["Fotos de Procedimento - Portal do Cliente"])


@router.get(
    "/tenants/{slug}/procedure-history/{procedure_id}/photos",
    response_model=List[ProcedurePhotoCustomerResponse],
)
def list_customer_visible_photos(
    slug: str,
    procedure_id: str,
    db: Session = Depends(get_db),
    current_customer: CustomerAccount = Depends(get_current_customer),
):
    tenant: Tenant = get_public_tenant_by_slug(slug, db)
    return procedure_photo_service.list_customer_visible_photos(
        db=db,
        tenant_id=tenant.id,
        procedure_id=uuid.UUID(procedure_id),
        customer_account_id=current_customer.id,
    )
