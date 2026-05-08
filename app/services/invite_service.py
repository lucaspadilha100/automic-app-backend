from datetime import datetime, timezone, timedelta
import secrets
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.core.exceptions import NotFoundError, ValidationError
from app.models.user import User, UserInvite
from app.services.audit_service import audit_service


class InviteService:
    """Business logic for internal user invitations."""

    def create_invite(self, db: Session, tenant_id, email: str, role: str, invited_by_user_id, phone=None, expires_hours: int = 72) -> UserInvite:
        token = secrets.token_urlsafe(32)
        invite = UserInvite(
            tenant_id=tenant_id,
            email=email,
            phone=phone,
            role=role,
            invited_by_user_id=invited_by_user_id,
            token=token,
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_hours),
        )
        db.add(invite)
        db.flush()
        audit_service.log(db, "user_invite_created", "user_invite", invite.id, tenant_id, invited_by_user_id)
        return invite

    def accept_invite(self, db: Session, token: str, name: str, password: str) -> User:
        invite = db.query(UserInvite).filter(UserInvite.token == token).first()
        if not invite:
            raise NotFoundError("INVITE_NOT_FOUND", "Convite não encontrado.")
        if invite.status != "pending" or invite.expires_at < datetime.now(timezone.utc):
            raise ValidationError("Convite expirado ou inválido.")
        user = User(
            tenant_id=invite.tenant_id,
            email=invite.email,
            phone=invite.phone,
            name=name,
            role=invite.role,
            password_hash=hash_password(password),
            is_active=True,
        )
        db.add(user)
        invite.status = "accepted"
        invite.accepted_at = datetime.now(timezone.utc)
        db.flush()
        audit_service.log(db, "user_invite_accepted", "user_invite", invite.id, invite.tenant_id, user.id)
        return user


invite_service = InviteService()
