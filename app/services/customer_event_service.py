from datetime import datetime, timezone
from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.event import CustomerEvent


class CustomerEventService:
    def emit(
        self,
        db: Session,
        event_type: str,
        tenant_id: UUID,
        customer_account_id: Optional[UUID] = None,
        tenant_customer_id: Optional[UUID] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CustomerEvent:
        event = CustomerEvent(
            tenant_id=tenant_id,
            customer_account_id=customer_account_id,
            tenant_customer_id=tenant_customer_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_=metadata,
            created_at=datetime.now(timezone.utc),
        )
        db.add(event)
        db.flush()

        # Process automation rules — never breaks the caller's flow
        try:
            from app.services.automation_service import automation_service
            automation_service.process_customer_event(db, event)
        except Exception:
            pass

        return event


customer_event_service = CustomerEventService()
