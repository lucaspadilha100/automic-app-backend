from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid
from datetime import datetime, timezone

from db.session import get_db
from app.core.dependencies import (
    get_current_user, require_active_tenant, require_manager_or_above,
)
from app.core.exceptions import PackageNotFoundError, CustomerPackageNotFoundError
from app.models.user import User
from app.models.tenant import Tenant
from app.models.package import Package, PackageService as PackageServiceModel, CustomerPackage, PackageSession
from app.services.plan_limit_service import plan_limit_service
from app.services.feature_flag_service import feature_flag_service
from app.services.audit_service import audit_service
from app.schemas.schemas import PackageCreate, PackageUpdate, PackageResponse, PackageServicePayload, PackageServiceResponse

router = APIRouter(prefix="/packages", tags=["Pacotes"])


@router.post("", response_model=PackageResponse)
def create_package(
    payload: PackageCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    feature_flag_service.require_feature(db, tenant, "packages")
    plan_limit_service.check_package_limit(db, tenant)

    pkg = Package(
        tenant_id=tenant.id,
        name=payload.name,
        description=payload.description,
        total_sessions=payload.total_sessions,
        price=payload.price,
        validity_days=payload.validity_days,
        service_ids=[str(sid) for sid in payload.service_ids] if payload.service_ids else None,
    )
    db.add(pkg)
    db.flush()
    if payload.service_ids:
        for sid in payload.service_ids:
            db.add(PackageServiceModel(tenant_id=tenant.id, package_id=pkg.id, service_id=sid, created_at=datetime.now(timezone.utc)))
    audit_service.log(db, "package_created", "package", pkg.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(pkg)
    return pkg


@router.get("", response_model=List[PackageResponse])
def list_packages(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(Package).filter(
        Package.tenant_id == tenant.id, Package.deleted_at.is_(None)
    ).all()


@router.get("/{package_id}/services", response_model=List[PackageServiceResponse])
def list_package_services(
    package_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pkg = db.query(Package).filter(Package.id == package_id, Package.tenant_id == tenant.id).first()
    if not pkg:
        raise PackageNotFoundError()
    return db.query(PackageServiceModel).filter(
        PackageServiceModel.tenant_id == tenant.id,
        PackageServiceModel.package_id == package_id,
    ).all()


@router.post("/{package_id}/services", response_model=List[PackageServiceResponse])
def add_package_services(
    package_id: uuid.UUID,
    payload: PackageServicePayload,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    pkg = db.query(Package).filter(Package.id == package_id, Package.tenant_id == tenant.id).first()
    if not pkg:
        raise PackageNotFoundError()
    existing = {str(row.service_id) for row in db.query(PackageServiceModel).filter(PackageServiceModel.tenant_id == tenant.id, PackageServiceModel.package_id == package_id).all()}
    for sid in payload.service_ids:
        if str(sid) not in existing:
            db.add(PackageServiceModel(tenant_id=tenant.id, package_id=package_id, service_id=sid, created_at=datetime.now(timezone.utc)))
            existing.add(str(sid))
    pkg.service_ids = list(existing)
    audit_service.log(db, "package_services_updated", "package", package_id, tenant.id, current_user.id)
    db.commit()
    return db.query(PackageServiceModel).filter(PackageServiceModel.tenant_id == tenant.id, PackageServiceModel.package_id == package_id).all()


@router.delete("/{package_id}/services/{service_id}")
def remove_package_service(
    package_id: uuid.UUID,
    service_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    deleted = db.query(PackageServiceModel).filter(
        PackageServiceModel.tenant_id == tenant.id,
        PackageServiceModel.package_id == package_id,
        PackageServiceModel.service_id == service_id,
    ).delete()
    pkg = db.query(Package).filter(Package.id == package_id, Package.tenant_id == tenant.id).first()
    if not pkg:
        raise PackageNotFoundError()
    remaining = db.query(PackageServiceModel).filter(PackageServiceModel.tenant_id == tenant.id, PackageServiceModel.package_id == package_id).all()
    pkg.service_ids = [str(row.service_id) for row in remaining]
    audit_service.log(db, "package_service_removed", "package", package_id, tenant.id, current_user.id)
    db.commit()
    return {"removed": bool(deleted)}


@router.get("/{package_id}", response_model=PackageResponse)
def get_package(
    package_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pkg = db.query(Package).filter(Package.id == package_id, Package.tenant_id == tenant.id).first()
    if not pkg:
        raise PackageNotFoundError()
    return pkg


@router.put("/{package_id}", response_model=PackageResponse)
def update_package(
    package_id: uuid.UUID,
    payload: PackageUpdate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    pkg = db.query(Package).filter(Package.id == package_id, Package.tenant_id == tenant.id).first()
    if not pkg:
        raise PackageNotFoundError()
    data = payload.model_dump(exclude_none=True)
    service_ids = data.pop("service_ids", None)
    for k, v in data.items():
        setattr(pkg, k, v)
    if service_ids is not None:
        pkg.service_ids = [str(sid) for sid in service_ids]
        db.query(PackageServiceModel).filter(PackageServiceModel.tenant_id == tenant.id, PackageServiceModel.package_id == pkg.id).delete()
        for sid in service_ids:
            db.add(PackageServiceModel(tenant_id=tenant.id, package_id=pkg.id, service_id=sid, created_at=datetime.now(timezone.utc)))
    audit_service.log(db, "package_updated", "package", pkg.id, tenant.id, current_user.id)
    db.commit()
    db.refresh(pkg)
    return pkg


@router.delete("/{package_id}")
def delete_package(
    package_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    pkg = db.query(Package).filter(Package.id == package_id, Package.tenant_id == tenant.id).first()
    if not pkg:
        raise PackageNotFoundError()
    pkg.deleted_at = datetime.now(timezone.utc)
    pkg.is_active = False
    db.commit()
    return {"message": "Pacote removido."}


# ---- Customer Packages (cross-reference) ----

@router.get("/customer-packages/{customer_package_id}")
def get_customer_package(
    customer_package_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cp = db.query(CustomerPackage).filter(
        CustomerPackage.id == customer_package_id, CustomerPackage.tenant_id == tenant.id
    ).first()
    if not cp:
        raise CustomerPackageNotFoundError()
    return cp


@router.patch("/customer-packages/{customer_package_id}/payment")
def update_customer_package_payment(
    customer_package_id: uuid.UUID,
    payment_status: str,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    cp = db.query(CustomerPackage).filter(
        CustomerPackage.id == customer_package_id, CustomerPackage.tenant_id == tenant.id
    ).first()
    if not cp:
        raise CustomerPackageNotFoundError()
    cp.payment_status = payment_status
    audit_service.log(db, "customer_package_payment_updated", "customer_package", cp.id, tenant.id, current_user.id)
    db.commit()
    return {"message": "Pagamento do pacote atualizado."}


@router.post("/customer-packages/{customer_package_id}/cancel")
def cancel_customer_package(
    customer_package_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    cp = db.query(CustomerPackage).filter(
        CustomerPackage.id == customer_package_id, CustomerPackage.tenant_id == tenant.id
    ).first()
    if not cp:
        raise CustomerPackageNotFoundError()
    cp.status = "cancelled"
    audit_service.log(db, "customer_package_cancelled", "customer_package", cp.id, tenant.id, current_user.id)
    db.commit()
    return {"message": "Pacote cancelado."}


@router.get("/customer-packages/{customer_package_id}/sessions")
def list_package_sessions(
    customer_package_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = db.query(PackageSession).filter(
        PackageSession.customer_package_id == customer_package_id,
        PackageSession.tenant_id == tenant.id,
    ).all()
    return sessions
