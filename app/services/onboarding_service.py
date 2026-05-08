"""
Self-service onboarding for new tenants.

Atomic flow:
  1. Validate slug uniqueness + email global uniqueness
  2. Create Tenant (status=trial)
  3. Create default settings/theme/booking_policy/payment_settings
  4. Create main Unit
  5. Create Starter subscription with trial_ends_at = now + TRIAL_DAYS
  6. Record terms acceptance
  7. Create owner User
  8. Emit OwnerNotification (best effort)

If anything fails midway, rollback the whole transaction so we don't leave
half-created tenants behind.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
import logging

from sqlalchemy.orm import Session

from app.models.tenant import (
    Tenant, TenantSubscription, TenantSettings, TenantTheme,
    TenantBookingPolicy, TenantPaymentSettings,
)
from app.models.user import User
from app.models.plan import Plan
from app.models.platform_document import PlatformDocument, PlatformDocumentType
from app.core.security import hash_password
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.services.unit_service import unit_service
from app.services.owner_notification_service import owner_notification_service

logger = logging.getLogger(__name__)

TRIAL_DAYS_DEFAULT = 14


class OnboardingService:
    def signup_tenant(
        self,
        db: Session,
        company_name: str,
        slug: str,
        owner_name: str,
        owner_email: str,
        owner_password: str,
        timezone_name: str = "America/Sao_Paulo",
        phone: Optional[str] = None,
        trial_days: int = TRIAL_DAYS_DEFAULT,
    ) -> Tuple[Tenant, User, TenantSubscription, Optional[str]]:
        """
        Creates a new tenant + default config + main unit + starter subscription
        + owner user, all in one transaction.

        Returns (tenant, owner_user, subscription, accepted_terms_version).
        """
        slug = slug.lower().strip()
        owner_email = owner_email.lower().strip()

        # ── Pre-checks ──────────────────────────────────────────────────────
        if db.query(Tenant).filter(Tenant.slug == slug).first():
            raise ConflictError(code="SLUG_TAKEN", message=f"Slug '{slug}' já está em uso.")

        # Email is unique (tenant_id, email). For signup we want stronger:
        # the same email shouldn't already own another tenant. Using a global
        # check among tenant_owner role across all tenants.
        existing_owner = (
            db.query(User)
            .filter(
                User.email == owner_email,
                User.role.in_(("super_admin", "tenant_owner")),
                User.deleted_at.is_(None),
            )
            .first()
        )
        if existing_owner:
            raise ConflictError(
                code="EMAIL_TAKEN",
                message=f"O email '{owner_email}' já está em uso por outra conta.",
            )

        # Pick the default plan (Starter) for self-service signups.
        plan = (
            db.query(Plan)
            .filter(Plan.name.in_(("Starter", "Start")), Plan.is_active.is_(True))
            .order_by((Plan.name == "Starter").desc())
            .first()
        )
        if not plan:
            raise NotFoundError(
                code="PLAN_NOT_FOUND",
                message="Nenhum plano padrão (Starter) disponível. Contate o suporte.",
            )

        # Capture current ToS version (if any) to record acceptance.
        tos_doc = (
            db.query(PlatformDocument)
            .filter(PlatformDocument.document_type == PlatformDocumentType.terms_of_service)
            .first()
        )
        accepted_version = tos_doc.version if tos_doc else None

        now = datetime.now(timezone.utc)

        # ── Atomic creation ─────────────────────────────────────────────────
        try:
            tenant = Tenant(
                name=company_name.strip(),
                slug=slug,
                status="trial",
                timezone=timezone_name,
                email=owner_email,
                phone=phone,
            )
            db.add(tenant)
            db.flush()  # need tenant.id

            # Default companion records
            db.add(TenantSettings(tenant_id=tenant.id))
            db.add(TenantTheme(tenant_id=tenant.id))
            db.add(TenantBookingPolicy(tenant_id=tenant.id))
            db.add(TenantPaymentSettings(tenant_id=tenant.id))

            # Main unit
            unit_service.ensure_main_unit(db, tenant, flush=False)

            # Subscription on Starter trial
            sub = TenantSubscription(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status="trial",
                starts_at=now,
                trial_ends_at=now + timedelta(days=trial_days),
                accepted_terms_at=now,
                accepted_terms_version=accepted_version,
                signup_source="self_service",
                # Default to manual billing for self-service signups — the owner
                # decides per-tenant when to switch to 'automatic' (Mercado Pago)
                # or 'free' (VIP/founder pricing).
                billing_mode="manual",
            )
            db.add(sub)

            # Owner user
            owner = User(
                tenant_id=tenant.id,
                email=owner_email,
                name=owner_name.strip(),
                role="tenant_owner",
                password_hash=hash_password(owner_password),
            )
            db.add(owner)
            db.flush()

            # Audit + notification (best-effort, must NOT abort the txn)
            try:
                owner_notification_service.emit_tenant_signup(db, tenant.id, tenant.name)
            except Exception as e:
                logger.warning("Owner notification on signup failed: %s", e)

            # Welcome email to the new owner (best-effort)
            try:
                from app.services.notification_service import notification_service
                notification_service.send_generic(
                    db, tenant_id=tenant.id, channel="email",
                    event_type="tenant_welcome", to=owner_email,
                    context={
                        "owner_name": owner.name,
                        "tenant_name": tenant.name,
                        "tenant_slug": tenant.slug,
                        "trial_days_left": trial_days,
                    },
                )
            except Exception as e:
                logger.warning("Welcome email failed: %s", e)

            db.commit()
            db.refresh(tenant)
            db.refresh(owner)
            db.refresh(sub)
            return tenant, owner, sub, accepted_version
        except Exception:
            db.rollback()
            raise


onboarding_service = OnboardingService()
