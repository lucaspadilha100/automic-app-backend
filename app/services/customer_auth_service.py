from datetime import datetime, timezone, timedelta
from typing import Optional
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, decode_token, generate_reset_token,
)
from app.core.exceptions import InvalidCredentialsError, TokenExpiredError, UnauthorizedError, ConflictError
from app.models.customer import CustomerAccount
from app.models.user import PasswordResetToken


class CustomerAuthService:

    def register(
        self, db: Session, name: str, phone: str, password: str, email: Optional[str] = None
    ) -> CustomerAccount:
        # Check uniqueness
        if email:
            exists = db.query(CustomerAccount).filter(CustomerAccount.email == email).first()
            if exists:
                raise ConflictError("CUSTOMER_EMAIL_TAKEN", "Este e-mail já está em uso.")
        exists_phone = db.query(CustomerAccount).filter(CustomerAccount.phone == phone).first()
        if exists_phone:
            raise ConflictError("CUSTOMER_PHONE_TAKEN", "Este telefone já está em uso.")

        customer = CustomerAccount(
            name=name,
            email=email,
            phone=phone,
            password_hash=hash_password(password),
        )
        db.add(customer)
        db.flush()
        return customer

    def authenticate(self, db: Session, login: str, password: str) -> CustomerAccount:
        """Login by email or phone."""
        customer = (
            db.query(CustomerAccount)
            .filter(
                (CustomerAccount.email == login) | (CustomerAccount.phone == login),
                CustomerAccount.is_active == True,
            )
            .first()
        )
        if not customer or not verify_password(password, customer.password_hash):
            raise InvalidCredentialsError()
        return customer

    def create_tokens(self, customer: CustomerAccount) -> dict:
        payload = {
            "sub": str(customer.id),
            "type": "customer",
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
            customer_id = payload.get("sub")
            customer = db.query(CustomerAccount).filter(CustomerAccount.id == customer_id, CustomerAccount.is_active == True).first()
            if not customer:
                raise UnauthorizedError()
            return self.create_tokens(customer)
        except JWTError:
            raise TokenExpiredError()

    def create_reset_token(self, db: Session, customer: CustomerAccount) -> str:
        token = generate_reset_token()
        prt = PasswordResetToken(
            customer_account_id=customer.id,
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
        customer = db.query(CustomerAccount).filter(CustomerAccount.id == prt.customer_account_id).first()
        if not customer:
            raise UnauthorizedError()
        customer.password_hash = hash_password(new_password)
        prt.used_at = datetime.now(timezone.utc)


customer_auth_service = CustomerAuthService()
