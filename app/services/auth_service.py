from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, decode_token, generate_reset_token,
)
from app.core.exceptions import InvalidCredentialsError, TokenExpiredError, UnauthorizedError
from app.models.user import User, PasswordResetToken


class AuthService:

    def authenticate(self, db: Session, email: str, password: str, tenant_id: Optional[UUID] = None) -> User:
        query = db.query(User).filter(User.email == email, User.is_active == True, User.deleted_at.is_(None))
        if tenant_id:
            query = query.filter(User.tenant_id == tenant_id)
        user = query.first()
        if not user or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError()
        return user

    def create_tokens(self, user: User) -> dict:
        payload = {
            "sub": str(user.id),
            "role": user.role,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "type": "internal",
        }
        return {
            "access_token": create_access_token(payload),
            "refresh_token": create_refresh_token(payload),
            "token_type": "bearer",
        }

    def refresh_tokens(self, db: Session, refresh_token: str) -> dict:
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise TokenExpiredError()
            user_id = payload.get("sub")
            user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
            if not user:
                raise UnauthorizedError()
            return self.create_tokens(user)
        except JWTError:
            raise TokenExpiredError()

    def create_reset_token(self, db: Session, user: User) -> str:
        token = generate_reset_token()
        prt = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
            created_at=datetime.now(timezone.utc),
        )
        db.add(prt)
        db.flush()
        return token

    def reset_password(self, db: Session, token: str, new_password: str) -> None:
        prt = (
            db.query(PasswordResetToken)
            .filter(PasswordResetToken.token == token, PasswordResetToken.used_at.is_(None))
            .first()
        )
        if not prt or prt.expires_at < datetime.now(timezone.utc):
            raise UnauthorizedError("Token de redefinição inválido ou expirado.")
        user = db.query(User).filter(User.id == prt.user_id).first()
        if not user:
            raise UnauthorizedError()
        user.password_hash = hash_password(new_password)
        prt.used_at = datetime.now(timezone.utc)


auth_service = AuthService()
