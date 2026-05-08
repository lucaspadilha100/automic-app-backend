from sqlalchemy.orm import Session
from app.models.tenant import Tenant, TenantSubscription, TenantLimitOverride
from app.models.plan import Plan
from app.models.service import Service
from app.models.professional import Professional
from app.models.user import User
from app.models.package import Package
from app.models.unit import Unit
from app.models.appointment import Appointment
from app.core.exceptions import (
    ServiceLimitReachedError, ProfessionalLimitReachedError,
    UserLimitReachedError, PackageLimitReachedError, UnitLimitReachedError,
)
from datetime import datetime, timezone
from typing import Optional


class PlanLimitService:
    def _get_effective_limits(self, db: Session, tenant: Tenant) -> dict:
        """Returns effective limits: override > plan > None (unlimited)."""
        subscription = (
            db.query(TenantSubscription)
            .filter(TenantSubscription.tenant_id == tenant.id)
            .order_by(TenantSubscription.created_at.desc())
            .first()
        )
        plan = db.query(Plan).filter(Plan.id == subscription.plan_id).first() if subscription else None

        override = db.query(TenantLimitOverride).filter(TenantLimitOverride.tenant_id == tenant.id).first()

        def resolve(attr: str) -> Optional[int]:
            if override and getattr(override, attr) is not None:
                return getattr(override, attr)
            if plan and getattr(plan, attr) is not None:
                return getattr(plan, attr)
            return None  # unlimited

        return {
            "max_services": resolve("max_services"),
            "max_professionals": resolve("max_professionals"),
            "max_users": resolve("max_users"),
            "max_appointments_per_month": resolve("max_appointments_per_month"),
            "max_units": resolve("max_units"),
            "max_packages": resolve("max_packages"),
        }

    def check_service_limit(self, db: Session, tenant: Tenant) -> None:
        limits = self._get_effective_limits(db, tenant)
        max_services = limits["max_services"]
        if max_services is None:
            return
        count = (
            db.query(Service)
            .filter(Service.tenant_id == tenant.id, Service.deleted_at.is_(None))
            .count()
        )
        if count >= max_services:
            raise ServiceLimitReachedError()

    def check_professional_limit(self, db: Session, tenant: Tenant) -> None:
        limits = self._get_effective_limits(db, tenant)
        max_professionals = limits["max_professionals"]
        if max_professionals is None:
            return
        count = (
            db.query(Professional)
            .filter(Professional.tenant_id == tenant.id, Professional.deleted_at.is_(None))
            .count()
        )
        if count >= max_professionals:
            raise ProfessionalLimitReachedError()

    def check_user_limit(self, db: Session, tenant: Tenant) -> None:
        limits = self._get_effective_limits(db, tenant)
        max_users = limits["max_users"]
        if max_users is None:
            return
        count = (
            db.query(User)
            .filter(User.tenant_id == tenant.id, User.deleted_at.is_(None))
            .count()
        )
        if count >= max_users:
            raise UserLimitReachedError()

    def check_package_limit(self, db: Session, tenant: Tenant) -> None:
        limits = self._get_effective_limits(db, tenant)
        max_packages = limits["max_packages"]
        if max_packages is None:
            return
        count = (
            db.query(Package)
            .filter(Package.tenant_id == tenant.id, Package.deleted_at.is_(None))
            .count()
        )
        if count >= max_packages:
            raise PackageLimitReachedError()

    def check_unit_limit(self, db: Session, tenant: Tenant) -> None:
        limits = self._get_effective_limits(db, tenant)
        max_units = limits["max_units"]
        if max_units is None:
            return
        count = (
            db.query(Unit)
            .filter(Unit.tenant_id == tenant.id, Unit.deleted_at.is_(None))
            .count()
        )
        if count >= max_units:
            raise UnitLimitReachedError()

    def get_effective_limits(self, db: Session, tenant: Tenant) -> dict:
        return self._get_effective_limits(db, tenant)


plan_limit_service = PlanLimitService()
