from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.customer import TenantCustomer
from app.models.customer_lifecycle import TenantLifecycleSetting
from app.models.appointment import Appointment
from app.services.audit_service import audit_service
from app.services.customer_event_service import customer_event_service
from app.services.feature_flag_service import feature_flag_service
from app.core.exceptions import NotFoundError

FEATURE_KEY = "customer_lifecycle"

# Default thresholds if no setting row exists
_DEFAULTS = {
    "inactive_after_days": 90,
    "at_risk_after_days": 45,
    "recurring_min_appointments": 3,
    "vip_min_appointments": 5,
    "vip_min_total_spent": Decimal("1000"),
}


class CustomerLifecycleService:

    # ── Settings ───────────────────────────────────────────────────────────────

    def _get_or_create_settings(self, db: Session, tenant_id: UUID) -> TenantLifecycleSetting:
        s = db.query(TenantLifecycleSetting).filter(
            TenantLifecycleSetting.tenant_id == tenant_id
        ).first()
        if not s:
            s = TenantLifecycleSetting(
                tenant_id=tenant_id,
                **{k: v for k, v in _DEFAULTS.items()},
            )
            db.add(s)
            db.flush()
        return s

    def get_settings(self, db: Session, tenant) -> TenantLifecycleSetting:
        feature_flag_service.require_feature(db, tenant, FEATURE_KEY)
        return self._get_or_create_settings(db, tenant.id)

    def update_settings(
        self,
        db: Session,
        tenant,
        data: dict,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> TenantLifecycleSetting:
        feature_flag_service.require_feature(db, tenant, FEATURE_KEY)
        s = self._get_or_create_settings(db, tenant.id)
        old = {k: str(getattr(s, k)) for k in _DEFAULTS}
        for k, v in data.items():
            if v is not None:
                setattr(s, k, v)
        db.flush()
        audit_service.log(
            db=db, action="lifecycle_settings_updated", entity_type="tenant_lifecycle_setting",
            entity_id=s.id, tenant_id=tenant.id, user_id=user_id,
            old_values=old, new_values={k: str(getattr(s, k)) for k in _DEFAULTS},
            ip_address=ip_address, user_agent=user_agent,
        )
        db.commit()
        db.refresh(s)
        return s

    # ── Core status logic ──────────────────────────────────────────────────────

    def determine_status(
        self,
        tc: TenantCustomer,
        settings: TenantLifecycleSetting,
    ) -> str:
        now = datetime.now(timezone.utc)

        # VIP check first (sticky — don't downgrade without explicit reason)
        if tc.lifecycle_status == "vip":
            return "vip"

        try:
            count = int(tc.appointments_count or 0)
        except Exception:
            count = 0
        try:
            spent = Decimal(str(tc.total_spent or 0))
        except Exception:
            spent = Decimal(0)

        # Earn VIP
        try:
            vip_spent_threshold = Decimal(str(settings.vip_min_total_spent))
        except Exception:
            vip_spent_threshold = Decimal("1000")
        try:
            vip_min_appts = int(settings.vip_min_appointments)
            recurring_min = int(settings.recurring_min_appointments)
        except Exception:
            vip_min_appts = 5
            recurring_min = 3
        if count >= vip_min_appts or spent >= vip_spent_threshold:
            return "vip"

        # Earn recurring
        if count >= recurring_min:
            # Check not inactive/at_risk
            if tc.lifecycle_status not in ("inactive", "at_risk"):
                return "recurring"

        # New with no appointments
        if count == 0:
            return "new"

        # Evaluate based on last appointment date
        last = tc.last_appointment_at
        has_next = bool(tc.next_appointment_at and tc.next_appointment_at > now)

        if last:
            days_since = (now - last.replace(tzinfo=timezone.utc) if last.tzinfo is None else now - last).days
            if days_since > settings.inactive_after_days and not has_next:
                return "inactive"
            if days_since > settings.at_risk_after_days and not has_next:
                return "at_risk"

        # High no-show ratio can push to at_risk
        if count > 0 and tc.no_show_count >= max(2, count // 2):
            return "at_risk"

        if count >= recurring_min:
            return "recurring"

        return "active"

    def _apply_status(
        self,
        db: Session,
        tc: TenantCustomer,
        new_status: str,
    ) -> bool:
        """Apply new_status to tc. Emit customer_event if changed. Returns True if changed."""
        if tc.lifecycle_status == new_status:
            return False
        old = tc.lifecycle_status
        tc.lifecycle_status = new_status
        customer_event_service.emit(
            db=db,
            event_type="customer_lifecycle_updated",
            tenant_id=tc.tenant_id,
            customer_account_id=tc.customer_account_id,
            tenant_customer_id=tc.id,
            entity_type="tenant_customer",
            entity_id=tc.id,
            metadata={"previous_status": old, "new_status": new_status},
        )
        return True

    def _get_tc(self, db: Session, tenant_id: UUID, tenant_customer_id: UUID) -> TenantCustomer:
        tc = db.query(TenantCustomer).filter(
            TenantCustomer.id == tenant_customer_id,
            TenantCustomer.tenant_id == tenant_id,
        ).first()
        if not tc:
            raise NotFoundError("Cliente não encontrado neste tenant.")
        return tc

    def _recalculate_next_appointment(self, db: Session, tc: TenantCustomer) -> None:
        now = datetime.now(timezone.utc)
        next_appt = (
            db.query(Appointment)
            .filter(
                Appointment.tenant_id == tc.tenant_id,
                Appointment.tenant_customer_id == tc.id,
                Appointment.status.in_(["scheduled", "confirmed"]),
                Appointment.start_datetime > now,
            )
            .order_by(Appointment.start_datetime.asc())
            .first()
        )
        tc.next_appointment_at = next_appt.start_datetime if next_appt else None

    # ── Admin views ────────────────────────────────────────────────────────────

    def get_summary(self, db: Session, tenant) -> dict:
        feature_flag_service.require_feature(db, tenant, FEATURE_KEY)
        rows = (
            db.query(TenantCustomer.lifecycle_status, func.count(TenantCustomer.id))
            .filter(TenantCustomer.tenant_id == tenant.id)
            .group_by(TenantCustomer.lifecycle_status)
            .all()
        )
        counts = {r[0]: r[1] for r in rows}
        total = sum(counts.values())
        return {
            "new": counts.get("new", 0),
            "active": counts.get("active", 0),
            "recurring": counts.get("recurring", 0),
            "inactive": counts.get("inactive", 0),
            "at_risk": counts.get("at_risk", 0),
            "vip": counts.get("vip", 0),
            "total": total,
        }

    def list_customers(
        self,
        db: Session,
        tenant,
        lifecycle_status: Optional[str] = None,
        min_total_spent: Optional[Decimal] = None,
        max_total_spent: Optional[Decimal] = None,
        has_next_appointment: Optional[bool] = None,
        no_show_count_min: Optional[int] = None,
    ) -> List[TenantCustomer]:
        feature_flag_service.require_feature(db, tenant, FEATURE_KEY)
        q = db.query(TenantCustomer).filter(TenantCustomer.tenant_id == tenant.id)
        if lifecycle_status:
            q = q.filter(TenantCustomer.lifecycle_status == lifecycle_status)
        if min_total_spent is not None:
            q = q.filter(TenantCustomer.total_spent >= min_total_spent)
        if max_total_spent is not None:
            q = q.filter(TenantCustomer.total_spent <= max_total_spent)
        if has_next_appointment is True:
            q = q.filter(TenantCustomer.next_appointment_at.isnot(None))
        elif has_next_appointment is False:
            q = q.filter(TenantCustomer.next_appointment_at.is_(None))
        if no_show_count_min is not None:
            q = q.filter(TenantCustomer.no_show_count >= no_show_count_min)
        return q.order_by(TenantCustomer.lifecycle_status).all()

    def get_customer_lifecycle(self, db: Session, tenant, tenant_customer_id: UUID) -> TenantCustomer:
        feature_flag_service.require_feature(db, tenant, FEATURE_KEY)
        return self._get_tc(db, tenant.id, tenant_customer_id)

    def recalculate_customer(
        self,
        db: Session,
        tenant,
        tenant_customer_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> dict:
        feature_flag_service.require_feature(db, tenant, FEATURE_KEY)
        tc = self._get_tc(db, tenant.id, tenant_customer_id)
        settings = self._get_or_create_settings(db, tenant.id)
        self._recalculate_next_appointment(db, tc)
        prev = tc.lifecycle_status
        new = self.determine_status(tc, settings)
        changed = self._apply_status(db, tc, new)
        if changed:
            audit_service.log(
                db=db, action="lifecycle_manual_recalculate", entity_type="tenant_customer",
                entity_id=tc.id, tenant_id=tenant.id, user_id=user_id,
                old_values={"lifecycle_status": prev},
                new_values={"lifecycle_status": new},
            )
        db.commit()
        return {"tenant_customer_id": tc.id, "previous_status": prev, "current_status": new, "changed": changed}

    def recalculate_all(self, db: Session, tenant, user_id: Optional[UUID] = None) -> int:
        feature_flag_service.require_feature(db, tenant, FEATURE_KEY)
        settings = self._get_or_create_settings(db, tenant.id)
        tcs = db.query(TenantCustomer).filter(TenantCustomer.tenant_id == tenant.id).all()
        changed = 0
        for tc in tcs:
            self._recalculate_next_appointment(db, tc)
            new = self.determine_status(tc, settings)
            if self._apply_status(db, tc, new):
                changed += 1
        db.commit()
        return changed

    # ── Auto-hooks called from appointment_service ─────────────────────────────
    # These do NOT commit — caller owns the transaction.

    def register_appointment_created(self, db: Session, appointment: Appointment) -> None:
        if not appointment.tenant_customer_id:
            return
        tc = db.query(TenantCustomer).filter(
            TenantCustomer.id == appointment.tenant_customer_id,
            TenantCustomer.tenant_id == appointment.tenant_id,
        ).first()
        if not tc:
            return
        self._recalculate_next_appointment(db, tc)
        settings = self._get_or_create_settings(db, appointment.tenant_id)
        new = self.determine_status(tc, settings)
        self._apply_status(db, tc, new)

    def register_appointment_completed(self, db: Session, appointment: Appointment) -> None:
        if not appointment.tenant_customer_id:
            return
        tc = db.query(TenantCustomer).filter(
            TenantCustomer.id == appointment.tenant_customer_id,
            TenantCustomer.tenant_id == appointment.tenant_id,
        ).first()
        if not tc:
            return
        now = datetime.now(timezone.utc)
        tc.last_appointment_at = now
        tc.appointments_count = (tc.appointments_count or 0) + 1
        try:
            price = Decimal(str(appointment.total_price or 0))
        except Exception:
            price = Decimal(0)
        try:
            current_spent = Decimal(str(tc.total_spent or 0))
        except Exception:
            current_spent = Decimal(0)
        tc.total_spent = current_spent + price
        self._recalculate_next_appointment(db, tc)
        settings = self._get_or_create_settings(db, appointment.tenant_id)
        new = self.determine_status(tc, settings)
        self._apply_status(db, tc, new)

    def register_appointment_cancelled(self, db: Session, appointment: Appointment) -> None:
        if not appointment.tenant_customer_id:
            return
        tc = db.query(TenantCustomer).filter(
            TenantCustomer.id == appointment.tenant_customer_id,
            TenantCustomer.tenant_id == appointment.tenant_id,
        ).first()
        if not tc:
            return
        self._recalculate_next_appointment(db, tc)
        settings = self._get_or_create_settings(db, appointment.tenant_id)
        new = self.determine_status(tc, settings)
        self._apply_status(db, tc, new)

    def register_appointment_no_show(self, db: Session, appointment: Appointment) -> None:
        if not appointment.tenant_customer_id:
            return
        tc = db.query(TenantCustomer).filter(
            TenantCustomer.id == appointment.tenant_customer_id,
            TenantCustomer.tenant_id == appointment.tenant_id,
        ).first()
        if not tc:
            return
        tc.no_show_count = (tc.no_show_count or 0) + 1
        self._recalculate_next_appointment(db, tc)
        settings = self._get_or_create_settings(db, appointment.tenant_id)
        new = self.determine_status(tc, settings)
        self._apply_status(db, tc, new)

    def register_appointment_rescheduled(self, db: Session, appointment: Appointment) -> None:
        self.register_appointment_cancelled(db, appointment)


customer_lifecycle_service = CustomerLifecycleService()
