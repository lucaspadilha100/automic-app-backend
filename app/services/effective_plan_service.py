"""
Effective plan service.

Computes the *effective* commercial configuration for a tenant by combining:
  - the base plan (pricing, default features and limits)
  - per-tenant feature flags (TenantFeatureFlag) — manual ON/OFF override
  - per-tenant limit overrides (TenantLimitOverride) — manual numeric override
  - per-subscription custom price (TenantSubscription.custom_price_monthly)

The result tells callers, for every feature and every limit, what the
*current effective value* is and where it came from ("plan" or "manual_override").
"""
from decimal import Decimal
from typing import Optional, Dict, Any
import uuid

from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.tenant import (
    Tenant, TenantSubscription, TenantFeatureFlag, TenantLimitOverride,
)


# Map feature_key (used in TenantFeatureFlag.feature_key) → Plan boolean column.
# Keep this in sync with feature_flag_service.PLAN_FEATURE_MAP.
PLAN_FEATURE_MAP: Dict[str, str] = {
    "online_payment": "allow_online_payment",
    "packages": "allow_packages",
    "custom_terms": "allow_custom_terms",
    "advanced_reports": "allow_advanced_reports",
    "crm_integration": "allow_crm_integration",
    "before_after_photos": "allow_before_after_photos",
    "multi_unit": "allow_multi_unit",
    "waitlist": "allow_waitlist",
    "physical_resources": "allow_physical_resources",
    "webhooks": "allow_webhooks",
    "custom_forms": "allow_custom_forms",
    "customer_lifecycle": "allow_customer_lifecycle",
    "automation_rules": "allow_automation_rules",
    "whatsapp_integration": "allow_whatsapp_integration",
    "commissions": "allow_commissions",
}

LIMIT_KEYS = (
    "max_services",
    "max_professionals",
    "max_users",
    "max_appointments_per_month",
    "max_units",
    "max_packages",
)


class EffectivePlanService:
    """Compute the *effective* commercial configuration of a tenant."""

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _current_subscription(self, db: Session, tenant_id: uuid.UUID) -> Optional[TenantSubscription]:
        return (
            db.query(TenantSubscription)
            .filter(TenantSubscription.tenant_id == tenant_id)
            .order_by(TenantSubscription.created_at.desc())
            .first()
        )

    def _plan_for(self, db: Session, sub: Optional[TenantSubscription]) -> Optional[Plan]:
        if not sub:
            return None
        return db.query(Plan).filter(Plan.id == sub.plan_id).first()

    def _flag_for(
        self, db: Session, tenant_id: uuid.UUID, feature_key: str
    ) -> Optional[TenantFeatureFlag]:
        return (
            db.query(TenantFeatureFlag)
            .filter(
                TenantFeatureFlag.tenant_id == tenant_id,
                TenantFeatureFlag.feature_key == feature_key,
            )
            .first()
        )

    def _override_for(self, db: Session, tenant_id: uuid.UUID) -> Optional[TenantLimitOverride]:
        return (
            db.query(TenantLimitOverride)
            .filter(TenantLimitOverride.tenant_id == tenant_id)
            .first()
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def get_effective_features(
        self, db: Session, tenant_id: uuid.UUID
    ) -> Dict[str, Dict[str, Any]]:
        """Return {feature_key: {"enabled": bool, "source": "plan"|"manual_override"}} for every known feature."""
        sub = self._current_subscription(db, tenant_id)
        plan = self._plan_for(db, sub)
        out: Dict[str, Dict[str, Any]] = {}
        for feature_key, plan_attr in PLAN_FEATURE_MAP.items():
            flag = self._flag_for(db, tenant_id, feature_key)
            if flag is not None:
                out[feature_key] = {"enabled": bool(flag.enabled), "source": "manual_override"}
            else:
                enabled = bool(getattr(plan, plan_attr, False)) if plan else False
                out[feature_key] = {"enabled": enabled, "source": "plan"}
        return out

    def get_feature_source(
        self, db: Session, tenant_id: uuid.UUID, feature_key: str
    ) -> Optional[Dict[str, Any]]:
        """Return {"enabled", "source"} for one feature, or None if the key is unknown."""
        if feature_key not in PLAN_FEATURE_MAP:
            return None
        flag = self._flag_for(db, tenant_id, feature_key)
        if flag is not None:
            return {"enabled": bool(flag.enabled), "source": "manual_override"}
        sub = self._current_subscription(db, tenant_id)
        plan = self._plan_for(db, sub)
        plan_attr = PLAN_FEATURE_MAP[feature_key]
        enabled = bool(getattr(plan, plan_attr, False)) if plan else False
        return {"enabled": enabled, "source": "plan"}

    def get_effective_limits(
        self, db: Session, tenant_id: uuid.UUID
    ) -> Dict[str, Dict[str, Any]]:
        """Return {limit_key: {"value": int|None, "source": "plan"|"manual_override"}}."""
        sub = self._current_subscription(db, tenant_id)
        plan = self._plan_for(db, sub)
        override = self._override_for(db, tenant_id)
        out: Dict[str, Dict[str, Any]] = {}
        for key in LIMIT_KEYS:
            override_value = getattr(override, key, None) if override else None
            if override_value is not None:
                out[key] = {"value": int(override_value), "source": "manual_override"}
            else:
                plan_value = getattr(plan, key, None) if plan else None
                out[key] = {
                    "value": int(plan_value) if plan_value is not None else None,
                    "source": "plan",
                }
        return out

    def get_limit_source(
        self, db: Session, tenant_id: uuid.UUID, limit_key: str
    ) -> Optional[Dict[str, Any]]:
        if limit_key not in LIMIT_KEYS:
            return None
        override = self._override_for(db, tenant_id)
        override_value = getattr(override, limit_key, None) if override else None
        if override_value is not None:
            return {"value": int(override_value), "source": "manual_override"}
        sub = self._current_subscription(db, tenant_id)
        plan = self._plan_for(db, sub)
        plan_value = getattr(plan, limit_key, None) if plan else None
        return {
            "value": int(plan_value) if plan_value is not None else None,
            "source": "plan",
        }

    def get_effective_price(
        self, db: Session, tenant_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Return:
          {
            "plan_price_monthly": Decimal | None,
            "custom_price_monthly": Decimal | None,
            "effective_price_monthly": Decimal,
            "source": "plan" | "manual_override",
          }
        """
        sub = self._current_subscription(db, tenant_id)
        plan = self._plan_for(db, sub)
        plan_price = Decimal(plan.price_monthly) if plan and plan.price_monthly is not None else None
        custom_price = (
            Decimal(sub.custom_price_monthly)
            if sub and sub.custom_price_monthly is not None
            else None
        )
        if custom_price is not None:
            effective = custom_price
            source = "manual_override"
        else:
            effective = plan_price if plan_price is not None else Decimal("0")
            source = "plan"
        return {
            "plan_price_monthly": plan_price,
            "custom_price_monthly": custom_price,
            "effective_price_monthly": effective,
            "source": source,
        }

    def get_effective_plan(
        self, db: Session, tenant: Tenant
    ) -> Dict[str, Any]:
        """Aggregated payload returned by the master endpoint."""
        sub = self._current_subscription(db, tenant.id)
        plan = self._plan_for(db, sub)
        price = self.get_effective_price(db, tenant.id)
        features = self.get_effective_features(db, tenant.id)
        limits = self.get_effective_limits(db, tenant.id)

        plan_payload = None
        if plan:
            plan_payload = {
                "id": str(plan.id),
                "name": plan.name,
                "price_monthly": float(plan.price_monthly) if plan.price_monthly is not None else 0.0,
                "is_active": bool(plan.is_active),
            }

        subscription_payload = None
        if sub:
            subscription_payload = {
                "id": str(sub.id),
                "status": sub.status,
                "starts_at": sub.starts_at.isoformat() if sub.starts_at else None,
                "trial_ends_at": sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
                "ends_at": sub.ends_at.isoformat() if sub.ends_at else None,
                "contracted_at": sub.contracted_at.isoformat() if sub.contracted_at else None,
                "custom_price_monthly": (
                    float(sub.custom_price_monthly) if sub.custom_price_monthly is not None else None
                ),
                "custom_price_reason": sub.custom_price_reason,
                "billing_notes": sub.billing_notes,
                "effective_price_monthly": float(price["effective_price_monthly"]),
                "price_source": price["source"],
            }

        return {
            "tenant_id": str(tenant.id),
            "plan": plan_payload,
            "subscription": subscription_payload,
            "features": features,
            "limits": limits,
        }


effective_plan_service = EffectivePlanService()
