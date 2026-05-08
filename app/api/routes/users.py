from typing import List, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid

from db.session import get_db
from app.core.dependencies import (
    get_current_user, require_active_tenant,
    require_tenant_owner_or_above, require_manager_or_above,
)
from app.core.exceptions import NotFoundError, ConflictError, ForbiddenError
from app.core.security import hash_password, generate_invite_token
from app.models.user import User, UserInvite
from app.models.tenant import Tenant
from app.services.plan_limit_service import plan_limit_service
from app.services.audit_service import audit_service
from app.schemas.auth import UserResponse
from app.schemas.schemas import InviteCreate, InviteAccept

router = APIRouter(prefix="/users", tags=["Usuários"])

ALLOWED_ROLES = {"manager", "receptionist", "professional"}


@router.get("", response_model=List[UserResponse])
def list_users(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return db.query(User).filter(
        User.tenant_id == tenant.id, User.deleted_at.is_(None)
    ).all()


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant.id).first()
    if not user:
        raise NotFoundError("USER_NOT_FOUND", "Usuário não encontrado.")
    return user


@router.put("/{user_id}")
def update_user(
    user_id: uuid.UUID,
    name: Optional[str] = None,
    phone: Optional[str] = None,
    is_active: Optional[bool] = None,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant.id).first()
    if not user:
        raise NotFoundError("USER_NOT_FOUND", "Usuário não encontrado.")
    if name:
        user.name = name
    if phone:
        user.phone = phone
    if is_active is not None:
        user.is_active = is_active
    audit_service.log(db, "user_updated", "user", user.id, tenant.id, current_user.id)
    db.commit()
    return {"message": "Usuário atualizado."}


@router.delete("/{user_id}")
def delete_user(
    user_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_tenant_owner_or_above),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant.id).first()
    if not user:
        raise NotFoundError("USER_NOT_FOUND", "Usuário não encontrado.")
    if user.role == "tenant_owner":
        raise ForbiddenError("Não é possível remover o proprietário.")
    user.deleted_at = datetime.now(timezone.utc)
    user.is_active = False
    audit_service.log(db, "user_deleted", "user", user.id, tenant.id, current_user.id)
    db.commit()
    return {"message": "Usuário removido."}


# ---- Invites ----

@router.post("/invites")
def create_invite(
    payload: InviteCreate,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    if payload.role not in ALLOWED_ROLES:
        raise ForbiddenError(f"Papel inválido. Permitidos: {', '.join(ALLOWED_ROLES)}")

    plan_limit_service.check_user_limit(db, tenant)

    # Check for existing pending invite
    existing = db.query(UserInvite).filter(
        UserInvite.tenant_id == tenant.id,
        UserInvite.email == payload.email,
        UserInvite.status == "pending",
    ).first()
    if existing:
        raise ConflictError("INVITE_PENDING", "Já existe um convite pendente para este e-mail.")

    token = generate_invite_token()
    invite = UserInvite(
        tenant_id=tenant.id,
        email=payload.email,
        phone=payload.phone,
        role=payload.role,
        invited_by_user_id=current_user.id,
        token=token,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invite)
    audit_service.log(db, "user_invited", "user_invite", invite.id, tenant.id, current_user.id)
    db.commit()
    # In production: send invite email with link containing token
    return {"message": "Convite enviado.", "token": token, "expires_at": invite.expires_at.isoformat()}


@router.post("/invites/accept")
def accept_invite(
    payload: InviteAccept,
    db: Session = Depends(get_db),
):
    invite = db.query(UserInvite).filter(
        UserInvite.token == payload.token, UserInvite.status == "pending"
    ).first()
    if not invite or invite.expires_at < datetime.now(timezone.utc):
        raise NotFoundError("INVITE_NOT_FOUND", "Convite inválido ou expirado.")

    # Check email not already registered in tenant
    exists = db.query(User).filter(
        User.tenant_id == invite.tenant_id, User.email == invite.email
    ).first()
    if exists:
        raise ConflictError("USER_EXISTS", "E-mail já cadastrado nesta empresa.")

    user = User(
        tenant_id=invite.tenant_id,
        email=invite.email,
        name=payload.name,
        phone=invite.phone,
        role=invite.role,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    invite.status = "accepted"
    invite.accepted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return {"message": "Conta criada com sucesso.", "user_id": str(user.id)}


@router.get("/invites")
def list_invites(
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    return db.query(UserInvite).filter(UserInvite.tenant_id == tenant.id).all()
