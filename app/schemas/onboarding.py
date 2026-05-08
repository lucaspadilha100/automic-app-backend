"""Schemas for self-service tenant onboarding."""
import re
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
import uuid

# Slug rules:
#  - lowercase ASCII letters, digits, hyphens
#  - 3 to 63 chars
#  - cannot start/end with hyphen
#  - cannot contain consecutive hyphens
SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9]|-(?=[a-z0-9])){1,61}[a-z0-9]$")

# Reserved slugs that the system cannot give to tenants because they collide
# with API/UI/public routes. Keep in sync with reality.
RESERVED_SLUGS = frozenset({
    "admin", "api", "app", "auth", "automic", "billing", "console", "customer",
    "demo", "dashboard", "help", "login", "master", "platform", "public",
    "register", "settings", "signup", "support", "system", "tenant", "tenants",
    "user", "users", "www", "internal",
})


class TenantSignupRequest(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=200)
    slug: str = Field(..., min_length=3, max_length=63)
    owner_name: str = Field(..., min_length=2, max_length=150)
    owner_email: EmailStr
    owner_password: str = Field(..., min_length=8, max_length=128)
    accept_terms: bool
    timezone: str = "America/Sao_Paulo"
    phone: Optional[str] = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        v = v.lower().strip()
        if not SLUG_RE.match(v):
            raise ValueError(
                "Slug inválido. Use 3 a 63 caracteres, apenas letras minúsculas, "
                "números e hífens. Não pode começar/terminar com hífen.",
            )
        if v in RESERVED_SLUGS:
            raise ValueError(f"Slug '{v}' é reservado pelo sistema.")
        return v

    @field_validator("accept_terms")
    @classmethod
    def must_accept_terms(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Você precisa aceitar os termos para criar uma conta.")
        return v

    @field_validator("company_name", "owner_name")
    @classmethod
    def trim_required(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Não pode estar vazio.")
        return v


class TenantSignupResponse(BaseModel):
    tenant_id: uuid.UUID
    tenant_slug: str
    tenant_name: str
    owner_user_id: uuid.UUID
    owner_email: str
    plan_name: str
    trial_ends_at: Optional[datetime]
    accepted_terms_version: Optional[str]
    message: str = "Cadastro criado com sucesso. Faça login para começar."
