from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid

from db.session import get_db
from app.core.dependencies import (
    get_current_user, require_active_tenant, require_manager_or_above,
)
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.models.tenant import Tenant
from app.models.resource import Resource, ServiceResource, AppointmentResource
from app.services.feature_flag_service import feature_flag_service
from app.services.audit_service import audit_service
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/resources", tags=["Recursos Físicos"])


class ResourceCreate(BaseModel):
    name: str
    type: str = "other"
    description: Optional[str] = None
    unit_id: Optional[uuid.UUID] = None


class ResourceResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    description: Optional[str] = None
    unit_id: Optional[uuid.UUID] = None
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


@router.post("", response_model=ResourceResponse)
def create_resource(
    payload: ResourceCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    feature_flag_service.require_feature(db, tenant, "physical_resources")
    resource = Resource(tenant_id=tenant.id, **payload.model_dump())
    db.add(resource)
    audit_service.log(db, "resource_created", "resource", resource.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(resource)
    return resource


@router.get("", response_model=List[ResourceResponse])
def list_resources(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    feature_flag_service.require_feature(db, tenant, "physical_resources")
    return db.query(Resource).filter(
        Resource.tenant_id == tenant.id, Resource.is_active == True
    ).all()


@router.get("/{resource_id}", response_model=ResourceResponse)
def get_resource(
    resource_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    feature_flag_service.require_feature(db, tenant, "physical_resources")
    resource = db.query(Resource).filter(
        Resource.id == resource_id, Resource.tenant_id == tenant.id
    ).first()
    if not resource:
        raise NotFoundError("RESOURCE_NOT_FOUND", "Recurso não encontrado.")
    return resource


@router.put("/{resource_id}", response_model=ResourceResponse)
def update_resource(
    resource_id: uuid.UUID,
    payload: ResourceCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    feature_flag_service.require_feature(db, tenant, "physical_resources")
    resource = db.query(Resource).filter(
        Resource.id == resource_id, Resource.tenant_id == tenant.id
    ).first()
    if not resource:
        raise NotFoundError("RESOURCE_NOT_FOUND", "Recurso não encontrado.")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(resource, k, v)
    audit_service.log(db, "resource_updated", "resource", resource.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(resource)
    return resource


@router.delete("/{resource_id}")
def delete_resource(
    resource_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    feature_flag_service.require_feature(db, tenant, "physical_resources")
    resource = db.query(Resource).filter(
        Resource.id == resource_id, Resource.tenant_id == tenant.id
    ).first()
    if not resource:
        raise NotFoundError("RESOURCE_NOT_FOUND", "Recurso não encontrado.")
    resource.is_active = False
    audit_service.log(db, "resource_deleted", "resource", resource.id, tenant.id, current_user.id)
    db.commit()
    return {"message": "Recurso desativado."}


# ---- Vinculação: Serviço ↔ Recurso ----

@router.post("/services/{service_id}/resources/{resource_id}", tags=["Recursos Físicos"])
def link_resource_to_service(
    service_id: uuid.UUID,
    resource_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    feature_flag_service.require_feature(db, tenant, "physical_resources")
    exists = db.query(ServiceResource).filter(
        ServiceResource.service_id == service_id,
        ServiceResource.resource_id == resource_id,
        ServiceResource.tenant_id == tenant.id,
    ).first()
    if not exists:
        link = ServiceResource(
            tenant_id=tenant.id,
            service_id=service_id,
            resource_id=resource_id,
            created_at=datetime.now(timezone.utc),
        )
        db.add(link)
        db.commit()
    return {"message": "Recurso vinculado ao serviço."}


@router.delete("/services/{service_id}/resources/{resource_id}", tags=["Recursos Físicos"])
def unlink_resource_from_service(
    service_id: uuid.UUID,
    resource_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    feature_flag_service.require_feature(db, tenant, "physical_resources")
    db.query(ServiceResource).filter(
        ServiceResource.service_id == service_id,
        ServiceResource.resource_id == resource_id,
        ServiceResource.tenant_id == tenant.id,
    ).delete()
    db.commit()
    return {"message": "Vínculo removido."}


@router.get("/services/{service_id}/resources", tags=["Recursos Físicos"])
def get_service_resources(
    service_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    feature_flag_service.require_feature(db, tenant, "physical_resources")
    links = db.query(ServiceResource).filter(
        ServiceResource.service_id == service_id,
        ServiceResource.tenant_id == tenant.id,
    ).all()
    return {"resource_ids": [str(lk.resource_id) for lk in links]}
