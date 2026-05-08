import hmac
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.models.webhook import WebhookEndpoint, WebhookDelivery
from app.core.config import settings

logger = logging.getLogger(__name__)


class WebhookService:
    """
    Serviço de disparo de webhooks.

    Uso:
        webhook_service.dispatch(db, tenant_id, "appointment.created", payload)

    Em produção, mover para Celery/ARQ/BackgroundTasks para não bloquear a request.
    """

    def _sign_payload(self, secret: str, body: str) -> str:
        return hmac.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def dispatch(
        self,
        db: Session,
        tenant_id: UUID,
        event_type: str,
        payload: Dict[str, Any],
    ) -> None:
        if not settings.WEBHOOKS_ENABLED:
            return

        endpoints: List[WebhookEndpoint] = (
            db.query(WebhookEndpoint)
            .filter(
                WebhookEndpoint.tenant_id == tenant_id,
                WebhookEndpoint.is_active == True,
            )
            .all()
        )

        for endpoint in endpoints:
            # Filter by subscribed events
            if endpoint.event_types and event_type not in endpoint.event_types:
                continue

            delivery = WebhookDelivery(
                tenant_id=tenant_id,
                webhook_endpoint_id=endpoint.id,
                event_type=event_type,
                payload=payload,
                status="pending",
                attempt_count=0,
            )
            db.add(delivery)
            db.flush()

            # Fire synchronously for MVP; replace with background task in production
            self._send(db, delivery, endpoint)

    def _send(
        self,
        db: Session,
        delivery: WebhookDelivery,
        endpoint: WebhookEndpoint,
    ) -> None:
        body = json.dumps(delivery.payload, default=str)
        headers = {
            "Content-Type": "application/json",
            "X-Automic-Event": delivery.event_type,
            "X-Automic-Delivery": str(delivery.id),
        }

        if endpoint.secret:
            signature = self._sign_payload(endpoint.secret, body)
            headers["X-Automic-Signature"] = f"sha256={signature}"

        now = datetime.now(timezone.utc)
        delivery.attempt_count += 1
        delivery.last_attempt_at = now

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(endpoint.url, content=body, headers=headers)
            delivery.response_status = response.status_code
            delivery.response_body = response.text[:2000]
            delivery.status = "sent" if response.is_success else "failed"
        except Exception as exc:
            logger.warning(f"Webhook delivery {delivery.id} failed: {exc}")
            delivery.status = "failed"
            delivery.response_body = str(exc)[:2000]

    def retry_failed(self, db: Session, max_attempts: int = 3) -> int:
        """Reprocessa deliveries com falha. Chamar via cron/worker."""
        failed = (
            db.query(WebhookDelivery)
            .filter(
                WebhookDelivery.status == "failed",
                WebhookDelivery.attempt_count < max_attempts,
            )
            .all()
        )
        retried = 0
        for delivery in failed:
            endpoint = delivery.endpoint
            if endpoint and endpoint.is_active:
                delivery.status = "retrying"
                self._send(db, delivery, endpoint)
                retried += 1
        db.commit()
        return retried


webhook_service = WebhookService()
