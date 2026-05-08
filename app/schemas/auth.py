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
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


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
