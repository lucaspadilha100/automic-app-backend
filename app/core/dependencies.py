from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.security import decode_token
from app.core.exceptions import (
    UnauthorizedError, ForbiddenError, TenantNotFoundError,
    TenantInactiveError, TenantSuspendedError, TenantCancelledError,
    TokenExpiredError,
)
from app.models.user import User
from app.models.customer import CustomerAccount
from app.models.tenant import Tenant

bearer_scheme = HTTPBearer(auto_error=False)

INTERNAL_ROLES = {"super_admin", "tenant_owner", "manager", "receptionist", "professional"}
ACTIVE_TENANT_STATUSES = {"active", "trial"}


# ---- Token extraction helpers ----

def _decode_bearer(credentials: Optional[HTTPAuthorizationCredentials]) -> dict:
    if not credentials:
        raise UnauthorizedError()
    try:
        return decode_token(credentials.credentials)
    except JWTError:
        raise TokenExpiredError()


# ---- Internal user dependencies ----

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = _decode_bearer(credentials)
    # Internal access tokens may carry type="internal" (current auth_service)
    # or type="access" (legacy / generic). Both are accepted here.
    # type="customer" and type="refresh" are rejected.
    if payload.get("type") not in ("internal", "access", None) or payload.get("role") not in INTERNAL_ROLES:
        raise UnauthorizedError()
    user = db.query(User).filter(User.id == payload["sub"], User.is_active == True, User.deleted_at.is_(None)).first()
    if not user:
        raise UnauthorizedError()
    return user


def get_current_customer(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> CustomerAccount:
    payload = _decode_bearer(credentials)
    # Customer access tokens carry type="customer". For backward compatibility
    # we also accept legacy tokens where type was incorrectly "access" but no
    # internal user role is set — that path is gated by the lookup below
    # (we only return a CustomerAccount for the sub).
    token_type = str(payload.get("type", ""))
    if token_type not in ("customer", "access") or payload.get("role") in INTERNAL_ROLES:
        raise UnauthorizedError()
    customer = db.query(CustomerAccount).filter(
        CustomerAccount.id == payload["sub"], CustomerAccount.is_active == True
    ).first()
    if not customer:
        raise UnauthorizedError()
    return customer


def get_optional_customer(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[CustomerAccount]:
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
        token_type = str(payload.get("type", ""))
        if token_type not in ("customer", "access") or payload.get("role") in INTERNAL_ROLES:
            return None
        return db.query(CustomerAccount).filter(
            CustomerAccount.id == payload["sub"], CustomerAccount.is_active == True
        ).first()
    except Exception:
        return None


# ---- Role guards ----

def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "super_admin":
        raise ForbiddenError("Apenas o super_admin pode acessar este recurso.")
    return current_user


def require_tenant_owner_or_above(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("super_admin", "tenant_owner"):
        raise ForbiddenError()
    return current_user


def require_manager_or_above(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("super_admin", "tenant_owner", "manager"):
        raise ForbiddenError()
    return current_user


def require_receptionist_or_above(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("super_admin", "tenant_owner", "manager", "receptionist"):
        raise ForbiddenError()
    return current_user


# ---- Tenant resolution ----

def get_current_tenant(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Tenant:
    if current_user.role == "super_admin":
        raise ForbiddenError("super_admin deve usar rotas /master.")
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id, Tenant.deleted_at.is_(None)).first()
    if not tenant:
        raise TenantNotFoundError()
    return tenant


def require_active_tenant(tenant: Tenant = Depends(get_current_tenant)) -> Tenant:
    if tenant.status == "suspended":
        raise TenantSuspendedError()
    if tenant.status == "cancelled":
        raise TenantCancelledError()
    if tenant.status == "inactive":
        raise TenantInactiveError()
    return tenant


def get_public_tenant_by_slug(slug: str, db: Session = Depends(get_db)) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.slug == slug, Tenant.deleted_at.is_(None)).first()
    if not tenant:
        raise TenantNotFoundError()
    if tenant.status not in ACTIVE_TENANT_STATUSES:
        raise TenantInactiveError()
    return tenant


def get_tenant_by_id_for_master(tenant_id: str, db: Session = Depends(get_db)) -> Tenant:
    """Used by master routes; returns any tenant regardless of status."""
    import uuid
    try:
        tid = uuid.UUID(tenant_id)
    except ValueError:
        raise TenantNotFoundError()
    tenant = db.query(Tenant).filter(Tenant.id == tid, Tenant.deleted_at.is_(None)).first()
    if not tenant:
        raise TenantNotFoundError()
    return tenant


# ---- Tenant isolation check ----

def verify_tenant_access(user: User, tenant: Tenant) -> None:
    if user.role == "super_admin":
        return
    if str(user.tenant_id) != str(tenant.id):
        raise ForbiddenError()


# ---- Feature flag guard ----

def require_feature(feature_key: str):
    """
    Dependency factory that blocks the route with FEATURE_DISABLED when the
    feature is not enabled for the current tenant. Uses the effective flag
    (TenantFeatureFlag override, falling back to the plan default).
    """
    from app.services.feature_flag_service import feature_flag_service

    def _dep(
        tenant: Tenant = Depends(require_active_tenant),
        db: Session = Depends(get_db),
    ) -> Tenant:
        feature_flag_service.require_feature(db, tenant, feature_key)
        return tenant

    return _dep
