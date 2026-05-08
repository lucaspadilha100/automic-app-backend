from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid

from db.session import get_db
from app.core.dependencies import require_super_admin, get_tenant_by_id_for_master
from app.core.security import hash_password
from app.schemas.tenant import (
    TenantCreate, TenantUpdate, TenantStatusUpdate, TenantResponse,
    PlanCreate, PlanResponse, SubscriptionUpdate, LimitOverrideUpdate,
    FeatureFlagUpdate, TenantSettingsUpdate, TenantThemeUpdate, BookingPolicyUpdate
)
from app.models.user import User
from app.models.tenant import (
    Tenant, TenantSubscription, TenantLimitOverride, TenantFeatureFlag,
    TenantSettings, TenantTheme, TenantBookingPolicy, TenantPaymentSettings
)
from app.models.plan import Plan
from app.models.unit import Unit
from app.models.audit import AuditLog
from app.services.audit_service import audit_service
from app.services.owner_notification_service import owner_notification_service
from app.services.unit_service import unit_service
from app.services.effective_plan_service import effective_plan_service, LIMIT_KEYS
from datetime import datetime, timezone

router = APIRouter(prefix="/master", tags=["Console Master AUTOMIC"])


# ---- Tenants ----

@router.post("/tenants", response_model=TenantResponse)
def create_tenant(
    payload: TenantCreate,
    owner_email: Optional[str] = Query(None),
    owner_name: Optional[str] = Query(None),
    owner_password: Optional[str] = Query(None),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    tenant = Tenant(**payload.model_dump())
    db.add(tenant)
    db.flush()

    # Default settings required by the prompt.
    db.add(TenantSettings(tenant_id=tenant.id))
    db.add(TenantTheme(tenant_id=tenant.id))
    db.add(TenantBookingPolicy(tenant_id=tenant.id))
    db.add(TenantPaymentSettings(tenant_id=tenant.id))

    # Every tenant must start with a main unit, even when multi-unit is disabled.
    unit_service.ensure_main_unit(db, tenant, flush=False)

    # Default subscription when a seed/default plan exists. It can be changed later
    # through /master/tenants/{tenant_id}/subscription.
    default_plan = (
        db.query(Plan)
        .filter(Plan.name.in_(["Starter", "Start"]), Plan.is_active == True)
        .order_by((Plan.name == "Starter").desc())  # prefer Starter when both exist
        .first()
    )
    if default_plan:
        db.add(TenantSubscription(
            tenant_id=tenant.id,
            plan_id=default_plan.id,
            status="trial" if tenant.status == "trial" else "active",
            starts_at=datetime.now(timezone.utc),
        ))

    # Create tenant_owner user if provided
    if owner_email and owner_name and owner_password:
        owner = User(
            tenant_id=tenant.id,
            email=owner_email,
            name=owner_name,
            role="tenant_owner",
            password_hash=hash_password(owner_password),
        )
        db.add(owner)

    audit_service.log(db, "tenant_created", "tenant", tenant.id, user_id=current_user.id)
    # Owner notification — advisory, never breaks the flow
    owner_notification_service.emit_tenant_signup(db, tenant.id, tenant.name)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.get("/tenants", response_model=List[TenantResponse])
def list_tenants(
    status: Optional[str] = None,
    skip: int = 0, limit: int = 50,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    q = db.query(Tenant).filter(Tenant.deleted_at.is_(None))
    if status:
        q = q.filter(Tenant.status == status)
    return q.offset(skip).limit(limit).all()


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
def get_tenant(
    tenant: Tenant = Depends(get_tenant_by_id_for_master),
    current_user: User = Depends(require_super_admin),
):
    return tenant


@router.put("/tenants/{tenant_id}", response_model=TenantResponse)
def update_tenant(
    payload: TenantUpdate,
    tenant: Tenant = Depends(get_tenant_by_id_for_master),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(tenant, k, v)
    audit_service.log(db, "tenant_updated", "tenant", tenant.id, user_id=current_user.id)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.patch("/tenants/{tenant_id}/status")
def update_tenant_status(
    payload: TenantStatusUpdate,
    tenant: Tenant = Depends(get_tenant_by_id_for_master),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    old_status = tenant.status
    tenant.status = payload.status
    audit_service.log(db, f"tenant_{payload.status}", "tenant", tenant.id,
                      user_id=current_user.id, old_values={"status": old_status}, new_values={"status": payload.status})
    if old_status != payload.status:
        owner_notification_service.emit_tenant_status_change(
            db, tenant.id, tenant.name, old_status, payload.status,
        )
    db.commit()
    return {"message": f"Status atualizado para {payload.status}."}


# ---- Plans ----

@router.post("/plans", response_model=PlanResponse)
def create_plan(
    payload: PlanCreate,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    plan = Plan(**payload.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/plans", response_model=List[PlanResponse])
def list_plans(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return db.query(Plan).filter(Plan.is_active == True).all()




@router.get("/plans/{plan_id}", response_model=PlanResponse)
def get_plan(
    plan_id: uuid.UUID,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("PLAN_NOT_FOUND", "Plano não encontrado.")
    return plan


@router.put("/plans/{plan_id}", response_model=PlanResponse)
def update_plan(
    plan_id: uuid.UUID,
    payload: PlanCreate,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("PLAN_NOT_FOUND", "Plano não encontrado.")
    for k, v in payload.model_dump().items():
        setattr(plan, k, v)
    db.commit()
    db.refresh(plan)
    return plan


# ---- Subscription ----

@router.put("/tenants/{tenant_id}/subscription")
def update_subscription(
    payload: SubscriptionUpdate,
    tenant: Tenant = Depends(get_tenant_by_id_for_master),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    sub = db.query(TenantSubscription).filter(TenantSubscription.tenant_id == tenant.id).first()

    # Capture before-values for the audit log.
    before = {}
    if sub:
        before = {
            "plan_id": str(sub.plan_id),
            "status": sub.status,
            "custom_price_monthly": (
                float(sub.custom_price_monthly)
                if sub.custom_price_monthly is not None else None
            ),
            "custom_price_reason": sub.custom_price_reason,
            "billing_notes": sub.billing_notes,
            "contracted_at": sub.contracted_at.isoformat() if sub.contracted_at else None,
        }

    plan_changed = False
    price_changed = False

    if sub:
        if str(sub.plan_id) != str(payload.plan_id):
            plan_changed = True
        sub.plan_id = payload.plan_id
        if payload.status:
            sub.status = payload.status
        if payload.trial_ends_at:
            sub.trial_ends_at = payload.trial_ends_at
        if payload.ends_at:
            sub.ends_at = payload.ends_at
        # Commercial overrides
        if "custom_price_monthly" in payload.model_fields_set:
            old = sub.custom_price_monthly
            sub.custom_price_monthly = payload.custom_price_monthly
            if (old or 0) != (payload.custom_price_monthly or 0):
                price_changed = True
        if "custom_price_reason" in payload.model_fields_set:
            sub.custom_price_reason = payload.custom_price_reason
        if "billing_notes" in payload.model_fields_set:
            sub.billing_notes = payload.billing_notes
        if "contracted_at" in payload.model_fields_set:
            sub.contracted_at = payload.contracted_at
    else:
        sub = TenantSubscription(
            tenant_id=tenant.id,
            plan_id=payload.plan_id,
            status=payload.status or "active",
            starts_at=datetime.now(timezone.utc),
            trial_ends_at=payload.trial_ends_at,
            ends_at=payload.ends_at,
            custom_price_monthly=payload.custom_price_monthly,
            custom_price_reason=payload.custom_price_reason,
            billing_notes=payload.billing_notes,
            contracted_at=payload.contracted_at,
        )
        db.add(sub)
        plan_changed = True
        if payload.custom_price_monthly is not None:
            price_changed = True

    after = {
        "plan_id": str(payload.plan_id),
        "status": sub.status,
        "custom_price_monthly": (
            float(sub.custom_price_monthly)
            if sub.custom_price_monthly is not None else None
        ),
        "custom_price_reason": sub.custom_price_reason,
        "billing_notes": sub.billing_notes,
        "contracted_at": sub.contracted_at.isoformat() if sub.contracted_at else None,
    }

    # Generic subscription_updated log always fires.
    audit_service.log(
        db, "subscription_updated", "tenant", tenant.id,
        user_id=current_user.id, old_values=before, new_values=after,
    )
    if plan_changed:
        audit_service.log(
            db, "subscription_plan_changed", "tenant", tenant.id,
            user_id=current_user.id,
            old_values={"plan_id": before.get("plan_id")},
            new_values={"plan_id": after["plan_id"]},
        )
    if price_changed:
        audit_service.log(
            db, "subscription_custom_price_updated", "tenant", tenant.id,
            user_id=current_user.id,
            old_values={"custom_price_monthly": before.get("custom_price_monthly")},
            new_values={
                "custom_price_monthly": after["custom_price_monthly"],
                "custom_price_reason": after["custom_price_reason"],
            },
        )

    db.commit()
    return {"message": "Assinatura atualizada."}


# ---- Limit Overrides ----

@router.get("/tenants/{tenant_id}/limit-overrides")
def get_limit_overrides(
    tenant: Tenant = Depends(get_tenant_by_id_for_master),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    override = db.query(TenantLimitOverride).filter(TenantLimitOverride.tenant_id == tenant.id).first()
    return override or {}


@router.put("/tenants/{tenant_id}/limit-overrides")
def update_limit_overrides(
    payload: LimitOverrideUpdate,
    tenant: Tenant = Depends(get_tenant_by_id_for_master),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    override = db.query(TenantLimitOverride).filter(TenantLimitOverride.tenant_id == tenant.id).first()

    before = {}
    if override:
        before = {k: getattr(override, k) for k in LIMIT_KEYS}
        before["notes"] = override.notes

    new_data = payload.model_dump(exclude_none=True)

    if override:
        for k, v in new_data.items():
            setattr(override, k, v)
    else:
        override = TenantLimitOverride(tenant_id=tenant.id, **new_data)
        db.add(override)

    after = {k: getattr(override, k) for k in LIMIT_KEYS}
    after["notes"] = override.notes

    # Per-limit detailed audit, plus a general one.
    for k in LIMIT_KEYS:
        if before.get(k) != after.get(k):
            audit_service.log(
                db, "limit_override_changed", "tenant", tenant.id,
                user_id=current_user.id,
                old_values={k: before.get(k)},
                new_values={k: after.get(k)},
            )
    audit_service.log(
        db, "limit_override_updated", "tenant", tenant.id,
        user_id=current_user.id, old_values=before, new_values=after,
    )

    db.commit()
    return {"message": "Overrides atualizados."}


# ---- Feature Flags ----

@router.get("/tenants/{tenant_id}/features")
def get_features(
    tenant: Tenant = Depends(get_tenant_by_id_for_master),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """
    Returns the *effective* features for the tenant: every known feature key,
    its effective enabled state, and whether the value comes from the plan or
    a manual override.
    """
    return effective_plan_service.get_effective_features(db, tenant.id)


@router.put("/tenants/{tenant_id}/features")
def update_feature(
    payload: FeatureFlagUpdate,
    tenant: Tenant = Depends(get_tenant_by_id_for_master),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    flag = db.query(TenantFeatureFlag).filter(
        TenantFeatureFlag.tenant_id == tenant.id,
        TenantFeatureFlag.feature_key == payload.feature_key,
    ).first()

    old_enabled = flag.enabled if flag else None

    if flag:
        flag.enabled = payload.enabled
        flag.source = payload.source
    else:
        flag = TenantFeatureFlag(
            tenant_id=tenant.id,
            feature_key=payload.feature_key,
            enabled=payload.enabled,
            source=payload.source,
        )
        db.add(flag)

    audit_service.log(
        db, "feature_flag_updated", "tenant", tenant.id,
        user_id=current_user.id,
        old_values={"feature_key": payload.feature_key, "enabled": old_enabled},
        new_values={"feature_key": payload.feature_key, "enabled": payload.enabled, "source": payload.source},
    )
    db.commit()
    return {"message": f"Feature '{payload.feature_key}' atualizada."}


# ---- Effective plan (combined view) ----

@router.get("/tenants/{tenant_id}/effective-plan")
def get_effective_plan(
    tenant: Tenant = Depends(get_tenant_by_id_for_master),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """
    Combined view of the tenant's commercial configuration:
    base plan, subscription, effective price (custom or plan), and per-feature/per-limit
    effective values with their source ("plan" or "manual_override").
    """
    return effective_plan_service.get_effective_plan(db, tenant)


# ---- MRR metrics ----

@router.get("/metrics/mrr")
def get_mrr_metrics(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """
    Monthly Recurring Revenue across the whole platform.
    A tenant with a custom_price_monthly contributes that value;
    otherwise it contributes the plan's price_monthly.
    Only "active" tenants count toward total MRR.
    "trial", "suspended" and "cancelled" are reported separately.
    """
    # Latest subscription per tenant. Using a window-style approach via correlated subquery.
    # This stays portable across Postgres / SQLite without distinct on.
    latest_sub_id = (
        db.query(func.max(TenantSubscription.created_at))
        .filter(TenantSubscription.tenant_id == Tenant.id)
        .correlate(Tenant)
        .scalar_subquery()
    )
    rows = (
        db.query(Tenant, TenantSubscription, Plan)
        .outerjoin(
            TenantSubscription,
            (TenantSubscription.tenant_id == Tenant.id)
            & (TenantSubscription.created_at == latest_sub_id),
        )
        .outerjoin(Plan, Plan.id == TenantSubscription.plan_id)
        .filter(Tenant.deleted_at.is_(None))
        .all()
    )

    total_mrr = 0.0
    active = trial = suspended = cancelled = inactive = 0
    custom_price_count = 0
    by_plan: dict = {}  # plan_name → {count, mrr}
    contributing_count = 0

    for tenant, sub, plan in rows:
        status = tenant.status
        if status == "active":
            active += 1
        elif status == "trial":
            trial += 1
        elif status == "suspended":
            suspended += 1
        elif status == "cancelled":
            cancelled += 1
        elif status == "inactive":
            inactive += 1

        if not sub or not plan:
            continue

        custom = sub.custom_price_monthly
        plan_price = plan.price_monthly or 0
        if custom is not None:
            effective = float(custom)
            custom_price_count += 1
        else:
            effective = float(plan_price)

        # Only "active" tenants are counted toward MRR.
        if status == "active":
            total_mrr += effective
            contributing_count += 1
            slot = by_plan.setdefault(plan.name, {"count": 0, "mrr": 0.0})
            slot["count"] += 1
            slot["mrr"] += effective

    average = (total_mrr / contributing_count) if contributing_count else 0.0

    return {
        "total_mrr": round(total_mrr, 2),
        "active_tenants_count": active,
        "trial_tenants_count": trial,
        "suspended_tenants_count": suspended,
        "cancelled_tenants_count": cancelled,
        "inactive_tenants_count": inactive,
        "tenants_with_custom_price": custom_price_count,
        "average_revenue_per_tenant": round(average, 2),
        "mrr_by_plan": [
            {"plan_name": name, "tenants": v["count"], "mrr": round(v["mrr"], 2)}
            for name, v in sorted(by_plan.items())
        ],
    }


# ---- Settings & Theme ----



@router.get("/tenants/{tenant_id}/settings")
def get_settings(
    tenant: Tenant = Depends(get_tenant_by_id_for_master),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    settings = db.query(TenantSettings).filter(TenantSettings.tenant_id == tenant.id).first()
    if not settings:
        settings = TenantSettings(tenant_id=tenant.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.put("/tenants/{tenant_id}/settings")
def update_settings(
    payload: TenantSettingsUpdate,
    tenant: Tenant = Depends(get_tenant_by_id_for_master),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    settings = db.query(TenantSettings).filter(TenantSettings.tenant_id == tenant.id).first()
    if not settings:
        settings = TenantSettings(tenant_id=tenant.id)
        db.add(settings)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(settings, k, v)
    db.commit()
    return {"message": "Configurações atualizadas."}




@router.get("/tenants/{tenant_id}/theme")
def get_theme(
    tenant: Tenant = Depends(get_tenant_by_id_for_master),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    theme = db.query(TenantTheme).filter(TenantTheme.tenant_id == tenant.id).first()
    if not theme:
        theme = TenantTheme(tenant_id=tenant.id)
        db.add(theme)
        db.commit()
        db.refresh(theme)
    return theme


@router.put("/tenants/{tenant_id}/theme")
def update_theme(
    payload: TenantThemeUpdate,
    tenant: Tenant = Depends(get_tenant_by_id_for_master),
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    theme = db.query(TenantTheme).filter(TenantTheme.tenant_id == tenant.id).first()
    if not theme:
        theme = TenantTheme(tenant_id=tenant.id)
        db.add(theme)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(theme, k, v)
    db.commit()
    return {"message": "Tema atualizado."}


# ---- Audit Logs ----

@router.get("/tenants/{tenant_id}/audit-logs")
def get_audit_logs(
    tenant: Tenant = Depends(get_tenant_by_id_for_master),
    current_user: User = Depends(require_super_admin),
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db),
):
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.tenant_id == tenant.id)
        .order_by(AuditLog.created_at.desc())
        .offset(skip).limit(limit)
        .all()
    )
    return logs
