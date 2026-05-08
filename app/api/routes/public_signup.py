"""
Public self-service onboarding routes (no auth).

Anyone can hit POST /public/signup to create a new tenant + owner.
The tenant starts on the Starter plan in trial mode.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.session import get_db
from app.schemas.onboarding import TenantSignupRequest, TenantSignupResponse
from app.services.onboarding_service import onboarding_service

router = APIRouter(prefix="/public", tags=["Cadastro - Público"])


@router.post("/signup", response_model=TenantSignupResponse, status_code=201)
def signup(payload: TenantSignupRequest, db: Session = Depends(get_db)):
    tenant, owner, sub, accepted_version = onboarding_service.signup_tenant(
        db=db,
        company_name=payload.company_name,
        slug=payload.slug,
        owner_name=payload.owner_name,
        owner_email=payload.owner_email,
        owner_password=payload.owner_password,
        timezone_name=payload.timezone,
        phone=payload.phone,
    )
    return TenantSignupResponse(
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        tenant_name=tenant.name,
        owner_user_id=owner.id,
        owner_email=owner.email,
        plan_name=sub.plan.name if sub.plan else "Starter",
        trial_ends_at=sub.trial_ends_at,
        accepted_terms_version=accepted_version,
    )
