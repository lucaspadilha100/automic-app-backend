from sqlalchemy.orm import Session
from app.models.tenant import Tenant, TenantFeatureFlag, TenantSubscription
from app.models.plan import Plan
from app.core.exceptions import FeatureDisabledError


PLAN_FEATURE_MAP = {
    "allow_online_payment": "online_payment",
    "allow_packages": "packages",
    "allow_custom_terms": "custom_terms",
    "allow_advanced_reports": "advanced_reports",
    "allow_crm_integration": "crm_integration",
    "allow_before_after_photos": "before_after_photos",
    "allow_multi_unit": "multi_unit",
    "allow_waitlist": "waitlist",
    "allow_physical_resources": "physical_resources",
    "allow_webhooks": "webhooks",
    "allow_custom_forms": "custom_forms",
    "allow_customer_lifecycle": "customer_lifecycle",
    "allow_automation_rules": "automation_rules",
    "allow_whatsapp_integration": "whatsapp_integration",
    "allow_commissions": "commissions",
}


class FeatureFlagService:
    def is_enabled(self, db: Session, tenant: Tenant, feature_key: str) -> bool:
        # Check tenant-level override first
        flag = (
            db.query(TenantFeatureFlag)
            .filter(
                TenantFeatureFlag.tenant_id == tenant.id,
                TenantFeatureFlag.feature_key == feature_key,
            )
            .first()
        )
        if flag is not None:
            return flag.enabled

        # Fall back to plan features
        subscription = (
            db.query(TenantSubscription)
            .filter(TenantSubscription.tenant_id == tenant.id)
            .order_by(TenantSubscription.created_at.desc())
            .first()
        )
        if not subscription:
            return False

        plan = db.query(Plan).filter(Plan.id == subscription.plan_id).first()
        if not plan:
            return False

        # Match feature_key to plan attribute
        for attr, key in PLAN_FEATURE_MAP.items():
            if key == feature_key:
                return bool(getattr(plan, attr, False))

        return False

    def require_feature(self, db: Session, tenant: Tenant, feature_key: str) -> None:
        if not self.is_enabled(db, tenant, feature_key):
            raise FeatureDisabledError(feature_key)

    def get_all_flags(self, db: Session, tenant: Tenant) -> dict:
        flags = (
            db.query(TenantFeatureFlag)
            .filter(TenantFeatureFlag.tenant_id == tenant.id)
            .all()
        )
        return {f.feature_key: f.enabled for f in flags}


feature_flag_service = FeatureFlagService()
