from pydantic import ConfigDict
from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: Optional["UserResponse"] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: str
    tenant_id: Optional[uuid.UUID] = None
    tenant_slug: Optional[str] = None
    tenant_name: Optional[str] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_user(cls, user: object) -> "UserResponse":
        tenant = getattr(user, "tenant", None)
        return cls(
            id=getattr(user, "id"),
            name=getattr(user, "name"),
            email=getattr(user, "email"),
            role=getattr(user, "role"),
            tenant_id=getattr(user, "tenant_id", None),
            tenant_slug=getattr(tenant, "slug", None) if tenant else None,
            tenant_name=getattr(tenant, "name", None) if tenant else None,
            is_active=getattr(user, "is_active"),
        )


# Customer auth
class CustomerRegisterRequest(BaseModel):
    name: str
    phone: str
    password: str
    email: Optional[str] = None


class CustomerLoginRequest(BaseModel):
    login: str  # email or phone
    password: str


class CustomerResponse(BaseModel):
    id: uuid.UUID
    name: str
    phone: str
    email: Optional[str] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
