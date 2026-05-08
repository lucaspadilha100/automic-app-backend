import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.automation import AutomationRule, ActionType
from app.models.customer import CustomerTag, CustomerTagLink, CustomerNote, TenantCustomer
from app.models.event import CustomerEvent
from app.models.notification import NotificationLog
from app.models.webhook import WebhookEndpoint, WebhookDelivery
from app.core.exceptions import NotFoundError
from app.services.audit_service import audit_service
from app.services.feature_flag_service import feature_flag_service

logger = logging.getLogger(__name__)

FEATURE_KEY = "automation_rules"


class AutomationService:

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _require_feature(self, db: Session, tenant) -> None:
        feature_flag_service.require_feature(db, tenant, FEATURE_KEY)

    def _get_rule(self, db: Session, tenant_id: UUID, rule_id: UUID) -> AutomationRule:
        rule = db.query(AutomationRule).filter(
            AutomationRule.id == rule_id,
            AutomationRule.tenant_id == tenant_id,
        ).first()
        if not rule:
            raise NotFoundError("Regra de automação não encontrada.")
        return rule

    # ── CRUD ───────────────────────────────────────────────────────────────────

    def list_rules(
        self,
        db: Session,
        tenant,
        trigger_event: Optional[str] = None,
        action_type: Optional[ActionType] = None,
        is_active: Optional[bool] = None,
    ) -> List[AutomationRule]:
        self._require_feature(db, tenant)
        q = db.query(AutomationRule).filter(AutomationRule.tenant_id == tenant.id)
        if trigger_event:
            q = q.filter(AutomationRule.trigger_event == trigger_event)
        if action_type:
            q = q.filter(AutomationRule.action_type == action_type)
        if is_active is not None:
            q = q.filter(AutomationRule.is_active == is_active)
        return q.order_by(AutomationRule.created_at.desc()).all()

    def get_rule(self, db: Session, tenant, rule_id: UUID) -> AutomationRule:
        self._require_feature(db, tenant)
        return self._get_rule(db, tenant.id, rule_id)

    def create_rule(
        self,
        db: Session,
        tenant,
        data: dict,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AutomationRule:
        self._require_feature(db, tenant)
        rule = AutomationRule(tenant_id=tenant.id, **data)
        db.add(rule)
        db.flush()
        audit_service.log(
            db=db, action="automation_rule_created", entity_type="automation_rule",
            entity_id=rule.id, tenant_id=tenant.id, user_id=user_id,
            new_values={"name": rule.name, "trigger_event": rule.trigger_event,
                        "action_type": rule.action_type.value},
            ip_address=ip_address, user_agent=user_agent,
        )
        db.commit()
        db.refresh(rule)
        return rule

    def update_rule(
        self,
        db: Session,
        tenant,
        rule_id: UUID,
        data: dict,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AutomationRule:
        self._require_feature(db, tenant)
        rule = self._get_rule(db, tenant.id, rule_id)
        old = {"name": rule.name, "trigger_event": rule.trigger_event,
               "action_type": rule.action_type.value, "is_active": rule.is_active}
        for k, v in data.items():
            if v is not None:
                setattr(rule, k, v)
        db.flush()
        audit_service.log(
            db=db, action="automation_rule_updated", entity_type="automation_rule",
            entity_id=rule.id, tenant_id=tenant.id, user_id=user_id,
            old_values=old,
            new_values={"name": rule.name, "trigger_event": rule.trigger_event,
                        "action_type": rule.action_type.value, "is_active": rule.is_active},
            ip_address=ip_address, user_agent=user_agent,
        )
        db.commit()
        db.refresh(rule)
        return rule

    def set_rule_status(
        self,
        db: Session,
        tenant,
        rule_id: UUID,
        is_active: bool,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AutomationRule:
        self._require_feature(db, tenant)
        rule = self._get_rule(db, tenant.id, rule_id)
        old = rule.is_active
        rule.is_active = is_active
        db.flush()
        action = "automation_rule_activated" if is_active else "automation_rule_deactivated"
        audit_service.log(
            db=db, action=action, entity_type="automation_rule",
            entity_id=rule.id, tenant_id=tenant.id, user_id=user_id,
            old_values={"is_active": old}, new_values={"is_active": is_active},
            ip_address=ip_address, user_agent=user_agent,
        )
        db.commit()
        db.refresh(rule)
        return rule

    def delete_or_disable_rule(
        self,
        db: Session,
        tenant,
        rule_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        self._require_feature(db, tenant)
        rule = self._get_rule(db, tenant.id, rule_id)
        audit_service.log(
            db=db, action="automation_rule_deleted", entity_type="automation_rule",
            entity_id=rule.id, tenant_id=tenant.id, user_id=user_id,
            old_values={"name": rule.name},
            ip_address=ip_address, user_agent=user_agent,
        )
        db.delete(rule)
        db.commit()

    # ── Event processing ───────────────────────────────────────────────────────

    def conditions_match(self, conditions: Optional[Dict], event: CustomerEvent) -> bool:
        """Return True if all conditions match against the event."""
        if not conditions:
            return True
        metadata = event.metadata_ or {}
        for key, expected in conditions.items():
            if key.startswith("metadata."):
                field = key[len("metadata."):]
                actual = metadata.get(field)
            elif key == "event_type":
                actual = event.event_type
            elif key == "entity_type":
                actual = event.entity_type
            elif key == "entity_id":
                actual = str(event.entity_id) if event.entity_id else None
            elif key == "customer_account_id":
                actual = str(event.customer_account_id) if event.customer_account_id else None
            elif key == "tenant_customer_id":
                actual = str(event.tenant_customer_id) if event.tenant_customer_id else None
            else:
                actual = metadata.get(key)
            if str(actual) != str(expected):
                return False
        return True

    def process_customer_event(self, db: Session, event: CustomerEvent) -> None:
        """Process all active automation rules for this event. Never raises."""
        try:
            # Check feature flag — use tenant mock to avoid heavy query
            from app.models.tenant import Tenant
            tenant = db.query(Tenant).filter(Tenant.id == event.tenant_id).first()
            if not tenant:
                return
            if not feature_flag_service.is_enabled(db, tenant, FEATURE_KEY):
                return

            rules = db.query(AutomationRule).filter(
                AutomationRule.tenant_id == event.tenant_id,
                AutomationRule.trigger_event == event.event_type,
                AutomationRule.is_active == True,
            ).all()

            for rule in rules:
                try:
                    if self.conditions_match(rule.conditions, event):
                        self.execute_action(db, rule, event)
                except Exception as exc:
                    logger.warning(
                        "Automation rule %s failed (action=%s event=%s): %s",
                        rule.id, rule.action_type, event.event_type, exc,
                    )
        except Exception as exc:
            logger.warning("automation.process_customer_event failed silently: %s", exc)

    def execute_action(self, db: Session, rule: AutomationRule, event: CustomerEvent) -> None:
        if rule.action_type == ActionType.add_customer_tag:
            self.execute_add_customer_tag(db, rule, event)
        elif rule.action_type == ActionType.create_customer_note:
            self.execute_create_customer_note(db, rule, event)
        elif rule.action_type == ActionType.emit_webhook_event:
            self.execute_emit_webhook_event(db, rule, event)
        elif rule.action_type == ActionType.create_notification_log:
            self.execute_create_notification_log(db, rule, event)

    def execute_add_customer_tag(self, db: Session, rule: AutomationRule, event: CustomerEvent) -> None:
        tag_id = rule.action_config.get("tag_id")
        if not tag_id:
            return

        # Validate tag belongs to same tenant
        tag = db.query(CustomerTag).filter(
            CustomerTag.id == tag_id,
            CustomerTag.tenant_id == rule.tenant_id,
        ).first()
        if not tag:
            logger.warning("automation: tag %s not found in tenant %s", tag_id, rule.tenant_id)
            return

        tc_id = event.tenant_customer_id
        if not tc_id:
            return

        # Validate tenant_customer belongs to same tenant
        tc = db.query(TenantCustomer).filter(
            TenantCustomer.id == tc_id,
            TenantCustomer.tenant_id == rule.tenant_id,
        ).first()
        if not tc:
            return

        # Idempotent: skip if tag already applied
        existing = db.query(CustomerTagLink).filter(
            CustomerTagLink.tenant_customer_id == tc_id,
            CustomerTagLink.tag_id == tag_id,
        ).first()
        if existing:
            return

        link = CustomerTagLink(
            tenant_id=rule.tenant_id,
            tenant_customer_id=tc_id,
            tag_id=tag_id,
            created_at=datetime.now(timezone.utc),
        )
        db.add(link)
        db.flush()

    def execute_create_customer_note(self, db: Session, rule: AutomationRule, event: CustomerEvent) -> None:
        note_text = rule.action_config.get("note", "")
        visibility = rule.action_config.get("visibility", "internal")

        tc_id = event.tenant_customer_id
        if not tc_id:
            return

        tc = db.query(TenantCustomer).filter(
            TenantCustomer.id == tc_id,
            TenantCustomer.tenant_id == rule.tenant_id,
        ).first()
        if not tc:
            return

        note = CustomerNote(
            tenant_id=rule.tenant_id,
            tenant_customer_id=tc_id,
            content=note_text,
            note=note_text,
            is_internal=(visibility == "internal"),
            visibility=visibility,
            note_type="system",
        )
        db.add(note)
        db.flush()

    def execute_emit_webhook_event(self, db: Session, rule: AutomationRule, event: CustomerEvent) -> None:
        event_type = rule.action_config.get("event_type", "automation_triggered")

        endpoints = db.query(WebhookEndpoint).filter(
            WebhookEndpoint.tenant_id == rule.tenant_id,
            WebhookEndpoint.is_active == True,
        ).all()

        for endpoint in endpoints:
            # Check if endpoint listens to this event type
            allowed = endpoint.event_types or []
            if allowed and event_type not in allowed:
                continue

            delivery = WebhookDelivery(
                tenant_id=rule.tenant_id,
                webhook_endpoint_id=endpoint.id,
                event_type=event_type,
                payload={
                    "event_type": event_type,
                    "trigger_event": event.event_type,
                    "tenant_id": str(rule.tenant_id),
                    "automation_rule_id": str(rule.id),
                    "customer_account_id": str(event.customer_account_id) if event.customer_account_id else None,
                    "tenant_customer_id": str(event.tenant_customer_id) if event.tenant_customer_id else None,
                    "metadata": event.metadata_ or {},
                },
                status="pending",
                attempt_count=0,
            )
            db.add(delivery)
        db.flush()

    def execute_create_notification_log(self, db: Session, rule: AutomationRule, event: CustomerEvent) -> None:
        channel = rule.action_config.get("channel", "internal")
        event_type = rule.action_config.get("event_type", "automation_triggered")

        log = NotificationLog(
            tenant_id=rule.tenant_id,
            customer_account_id=event.customer_account_id,
            channel=channel,
            event_type=event_type,
            status="sent",
        )
        db.add(log)
        db.flush()


automation_service = AutomationService()
