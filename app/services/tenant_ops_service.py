"""
Jobs and computed views over the tenant base.

`expire_trials` sweeps tenants whose trial_ends_at < now and whose subscription
is still in 'trial' status, suspending the tenant and emitting an
OwnerNotification per affected tenant.

`compute_tenant_health` returns a per-tenant snapshot used by the master
health dashboard (last login, last appointment, churn risk).

Both functions are idempotent — calling repeatedly is safe.

Until the worker comes (Expansão 2), `expire_trials` is exposed at
POST /master/jobs/run-trial-expiration so the owner can run it manually
or call it from cron / a task scheduler outside the app.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.tenant import Tenant, TenantSubscription
from app.models.user import User
from app.models.appointment import Appointment
from app.services.owner_notification_service import owner_notification_service

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TenantOpsService:
    # ── Trial expiration ────────────────────────────────────────────────────
    def expire_trials(self, db: Session) -> Dict[str, Any]:
        """
        Suspend any tenant whose trial has ended.

        A tenant is considered an expired trial when ALL hold:
          - tenant.status == 'trial'
          - subscription.status == 'trial'
          - subscription.trial_ends_at < now

        On match: tenant.status = 'suspended', subscription.status = 'past_due',
        emits a tenant_suspended notification.

        Returns a summary dict with counts.
        """
        now = _utcnow()
        rows = (
            db.query(Tenant, TenantSubscription)
            .join(TenantSubscription, TenantSubscription.tenant_id == Tenant.id)
            .filter(
                Tenant.status == "trial",
                TenantSubscription.status == "trial",
                TenantSubscription.trial_ends_at.isnot(None),
                TenantSubscription.trial_ends_at < now,
                Tenant.deleted_at.is_(None),
            )
            .all()
        )

        suspended_count = 0
        for tenant, sub in rows:
            old_status = tenant.status
            tenant.status = "suspended"
            sub.status = "past_due"
            db.add(tenant)
            db.add(sub)
            try:
                owner_notification_service.emit_tenant_status_change(
                    db, tenant.id, tenant.name, old_status, "suspended",
                )
            except Exception as e:
                logger.warning("Failed notification on trial expiration: %s", e)
            suspended_count += 1

        if suspended_count:
            db.commit()
        return {
            "checked_at": now.isoformat(),
            "suspended_count": suspended_count,
            "tenants_suspended": [str(t.id) for t, _ in rows],
        }

    # ── Health snapshot ─────────────────────────────────────────────────────
    def compute_tenant_health(self, db: Session) -> List[Dict[str, Any]]:
        """
        Compute health snapshot for every non-deleted tenant.

        Returns a list of dicts with:
          - tenant_id, tenant_name, slug
          - status (tenant.status)
          - subscription_status (sub.status)
          - plan_name
          - days_to_trial_end (negative if already past)
          - last_login_at (most recent user login of this tenant)
          - last_appointment_at
          - appointments_last_30_days
          - churn_risk: 'low' | 'medium' | 'high' | 'critical'
        """
        now = _utcnow()
        thirty_days_ago = now - timedelta(days=30)
        seven_days_ago = now - timedelta(days=7)

        results: List[Dict[str, Any]] = []
        tenants = (
            db.query(Tenant)
            .filter(Tenant.deleted_at.is_(None))
            .order_by(Tenant.created_at.desc())
            .all()
        )

        for t in tenants:
            sub = (
                db.query(TenantSubscription)
                .filter(TenantSubscription.tenant_id == t.id)
                .order_by(TenantSubscription.created_at.desc())
                .first()
            )

            # User has no last_login_at column today; using updated_at as a
            # rough proxy for "user activity" (token refresh, profile edit, etc).
            # When auth is upgraded to track logins, switch to last_login_at.
            last_login = (
                db.query(func.max(User.updated_at))
                .filter(User.tenant_id == t.id, User.deleted_at.is_(None))
                .scalar()
            )

            try:
                last_appointment = (
                    db.query(func.max(Appointment.start_datetime))
                    .filter(Appointment.tenant_id == t.id)
                    .scalar()
                )
                appts_30 = (
                    db.query(func.count(Appointment.id))
                    .filter(
                        Appointment.tenant_id == t.id,
                        Appointment.start_datetime >= thirty_days_ago,
                    )
                    .scalar()
                ) or 0
            except Exception:
                last_appointment = None
                appts_30 = 0

            days_to_trial_end: Optional[int] = None
            if sub and sub.trial_ends_at:
                delta = sub.trial_ends_at - now
                days_to_trial_end = delta.days

            risk = self._classify_risk(
                tenant_status=t.status,
                subscription_status=sub.status if sub else None,
                last_login_at=last_login,
                last_appointment_at=last_appointment,
                appts_30=appts_30,
                days_to_trial_end=days_to_trial_end,
                seven_days_ago=seven_days_ago,
                thirty_days_ago=thirty_days_ago,
            )

            results.append({
                "tenant_id": str(t.id),
                "tenant_name": t.name,
                "slug": t.slug,
                "status": t.status,
                "subscription_status": sub.status if sub else None,
                "plan_name": sub.plan.name if sub and sub.plan else None,
                "trial_ends_at": sub.trial_ends_at.isoformat() if sub and sub.trial_ends_at else None,
                "days_to_trial_end": days_to_trial_end,
                "last_login_at": last_login.isoformat() if last_login else None,
                "last_appointment_at": last_appointment.isoformat() if last_appointment else None,
                "appointments_last_30_days": appts_30,
                "churn_risk": risk,
            })
        return results

    @staticmethod
    def _classify_risk(
        tenant_status: str,
        subscription_status: Optional[str],
        last_login_at: Optional[datetime],
        last_appointment_at: Optional[datetime],
        appts_30: int,
        days_to_trial_end: Optional[int],
        seven_days_ago: datetime,
        thirty_days_ago: datetime,
    ) -> str:
        # Critical: tenant is dead-or-dying
        if tenant_status in ("suspended", "cancelled", "inactive"):
            return "critical"
        if subscription_status in ("cancelled", "past_due"):
            return "critical"

        # High: trial about to expire OR no activity in 30+ days
        if days_to_trial_end is not None and 0 <= days_to_trial_end <= 3:
            return "high"
        no_activity_30 = (
            (last_login_at is None or last_login_at < thirty_days_ago)
            and (last_appointment_at is None or last_appointment_at < thirty_days_ago)
        )
        if no_activity_30:
            return "high"

        # Medium: activity in last 30 but not last 7
        recent_activity = (
            (last_login_at is not None and last_login_at >= seven_days_ago)
            or (last_appointment_at is not None and last_appointment_at >= seven_days_ago)
        )
        if not recent_activity:
            return "medium"

        return "low"


tenant_ops_service = TenantOpsService()
