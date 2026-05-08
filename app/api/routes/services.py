from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import uuid
from datetime import datetime, timezone

from db.session import get_db
from app.core.dependencies import (
    get_current_user, get_current_tenant, require_active_tenant,
    require_manager_or_above, require_receptionist_or_above,
)
from app.core.exceptions import NotFoundError, ConflictError, ServiceNotFoundError
from app.models.user import User
from app.models.tenant import Tenant
from app.models.service import Service, ServiceCategory, ProfessionalService
from app.services.plan_limit_service import plan_limit_service
from app.services.audit_service import audit_service
from app.schemas.schemas import (
    ServiceCreate, ServiceUpdate, ServiceResponse,
    ServiceCategoryCreate, ServiceCategoryResponse,
)

router = APIRouter(prefix="/services", tags=["Serviços"])


# ---- Categories ----

@router.post("/categories", response_model=ServiceCategoryResponse)
def create_category(
    payload: ServiceCategoryCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    exists = db.query(ServiceCategory).filter(
        ServiceCategory.tenant_id == tenant.id,
        ServiceCategory.name == payload.name,
    ).first()
    if exists:
        raise ConflictError("CATEGORY_NAME_TAKEN", "Já existe uma categoria com este nome.")
    cat = ServiceCategory(tenant_id=tenant.id, **payload.model_dump())
    db.add(cat)
    audit_service.log(db, "service_category_created", "service_category", cat.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(cat)
    return cat


@router.get("/categories", response_model=List[ServiceCategoryResponse])
def list_categories(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(ServiceCategory)
        .filter(ServiceCategory.tenant_id == tenant.id, ServiceCategory.is_active == True)
        .order_by(ServiceCategory.sort_order)
        .all()
    )


@router.put("/categories/{category_id}", response_model=ServiceCategoryResponse)
def update_category(
    category_id: uuid.UUID,
    payload: ServiceCategoryCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    cat = db.query(ServiceCategory).filter(
        ServiceCategory.id == category_id, ServiceCategory.tenant_id == tenant.id
    ).first()
    if not cat:
        raise NotFoundError("CATEGORY_NOT_FOUND", "Categoria não encontrada.")
    for k, v in payload.model_dump().items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    cat = db.query(ServiceCategory).filter(
        ServiceCategory.id == category_id, ServiceCategory.tenant_id == tenant.id
    ).first()
    if not cat:
        raise NotFoundError("CATEGORY_NOT_FOUND", "Categoria não encontrada.")
    cat.is_active = False
    db.commit()
    return {"message": "Categoria desativada."}


# ---- Services ----

@router.post("", response_model=ServiceResponse)
def create_service(
    payload: ServiceCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    plan_limit_service.check_service_limit(db, tenant)

    if payload.category_id:
        cat = db.query(ServiceCategory).filter(
            ServiceCategory.id == payload.category_id, ServiceCategory.tenant_id == tenant.id
        ).first()
        if not cat:
            raise NotFoundError("CATEGORY_NOT_FOUND", "Categoria não encontrada.")

    svc = Service(tenant_id=tenant.id, **payload.model_dump())
    db.add(svc)
    db.flush()
    audit_service.log(db, "service_created", "service", svc.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(svc)
    return svc


@router.get("", response_model=List[ServiceResponse])
def list_services(
    category_id: Optional[uuid.UUID] = None,
    active_only: bool = True,
    skip: int = 0,
    limit: int = 100,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Service).filter(Service.tenant_id == tenant.id, Service.deleted_at.is_(None))
    if active_only:
        q = q.filter(Service.is_active == True)
    if category_id:
        q = q.filter(Service.category_id == category_id)
    return q.offset(skip).limit(limit).all()


@router.get("/{service_id}", response_model=ServiceResponse)
def get_service(
    service_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = db.query(Service).filter(
        Service.id == service_id, Service.tenant_id == tenant.id, Service.deleted_at.is_(None)
    ).first()
    if not svc:
        raise ServiceNotFoundError()
    return svc


@router.put("/{service_id}", response_model=ServiceResponse)
def update_service(
    service_id: uuid.UUID,
    payload: ServiceUpdate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    svc = db.query(Service).filter(
        Service.id == service_id, Service.tenant_id == tenant.id, Service.deleted_at.is_(None)
    ).first()
    if not svc:
        raise ServiceNotFoundError()
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(svc, k, v)
    audit_service.log(db, "service_updated", "service", svc.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(svc)
    return svc


@router.delete("/{service_id}")
def delete_service(
    service_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    svc = db.query(Service).filter(
        Service.id == service_id, Service.tenant_id == tenant.id, Service.deleted_at.is_(None)
    ).first()
    if not svc:
        raise ServiceNotFoundError()
    svc.deleted_at = datetime.now(timezone.utc)
    svc.is_active = False
    audit_service.log(db, "service_deleted", "service", svc.id, tenant.id, current_user.id)
    db.commit()
    return {"message": "Serviço removido."}
