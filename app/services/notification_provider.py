"""
Abstraction over notification providers for transactional messages.

Three channels: email, sms, whatsapp. Each has its own pluggable provider.

Default in dev/CI: `MockNotificationProvider` records every send to an
in-memory list (useful for tests, plus the regular NotificationLog DB row
is created either way).

Real providers activate via env:
  - RESEND_API_KEY    → ResendEmailProvider
  - ZENVIA_API_KEY    → ZenviaSmsProvider
  - N8N_WEBHOOK_URL   → N8nWhatsAppProvider (already wired in app.services.whatsapp_*)

When env not set, the corresponding channel falls back to mock for that channel.
This means you can enable email production while keeping SMS in mock mode.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import logging
import os
import threading

logger = logging.getLogger(__name__)


@dataclass
class SendResult:
    success: bool
    provider: str
    provider_reference: Optional[str] = None
    error_message: Optional[str] = None
    raw_payload: Optional[dict] = None


@dataclass
class _RecordedSend:
    """In-memory record kept by MockNotificationProvider for inspection in tests."""
    channel: str
    to: str
    subject: Optional[str]
    body: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class NotificationProvider:
    """Abstract interface — three channels, all optional to override."""

    name = "abstract"

    def send_email(
        self, to: str, subject: str, body: str,
        from_email: Optional[str] = None, **meta,
    ) -> SendResult:
        raise NotImplementedError

    def send_sms(self, to: str, body: str, **meta) -> SendResult:
        raise NotImplementedError

    def send_whatsapp(self, to: str, body: str, **meta) -> SendResult:
        raise NotImplementedError


# ── Mock ──────────────────────────────────────────────────────────────────────

class MockNotificationProvider(NotificationProvider):
    """In-memory provider — records every send for test inspection."""

    name = "mock"

    def __init__(self):
        self._lock = threading.Lock()
        self._sent: List[_RecordedSend] = []

    @property
    def sent(self) -> List[_RecordedSend]:
        with self._lock:
            return list(self._sent)

    def reset(self):
        with self._lock:
            self._sent.clear()

    def send_email(self, to, subject, body, from_email=None, **meta):
        with self._lock:
            self._sent.append(_RecordedSend("email", to, subject, body, meta))
        logger.debug("[mock email] to=%s subj=%s", to, subject)
        return SendResult(success=True, provider=self.name, provider_reference=f"mock-em-{len(self._sent)}")

    def send_sms(self, to, body, **meta):
        with self._lock:
            self._sent.append(_RecordedSend("sms", to, None, body, meta))
        logger.debug("[mock sms] to=%s", to)
        return SendResult(success=True, provider=self.name, provider_reference=f"mock-sms-{len(self._sent)}")

    def send_whatsapp(self, to, body, **meta):
        with self._lock:
            self._sent.append(_RecordedSend("whatsapp", to, None, body, meta))
        logger.debug("[mock whatsapp] to=%s", to)
        return SendResult(success=True, provider=self.name, provider_reference=f"mock-wa-{len(self._sent)}")


# ── Resend (email) ────────────────────────────────────────────────────────────

class ResendEmailProvider(NotificationProvider):
    """
    Skeleton for Resend (https://resend.com).

    Activates when RESEND_API_KEY is set. To send, the implementation does:
        POST https://api.resend.com/emails
        Authorization: Bearer {RESEND_API_KEY}
        Body: {"from": ..., "to": [...], "subject": ..., "html": ...}

    For now sends are NOT made to avoid accidentally hitting the real API
    in dev — `_make_request` is the toggle. Set RESEND_LIVE=1 plus the API key
    to actually send. This protects the user from blowing through quota.
    """

    name = "resend"

    def __init__(self, api_key: Optional[str] = None, default_from: Optional[str] = None):
        self.api_key = api_key or os.environ.get("RESEND_API_KEY")
        self.default_from = default_from or os.environ.get(
            "RESEND_FROM_EMAIL", "noreply@automic.tech",
        )
        self.live = os.environ.get("RESEND_LIVE") == "1"

    def _require(self):
        if not self.api_key:
            raise RuntimeError("RESEND_API_KEY não configurado.")

    def send_email(self, to, subject, body, from_email=None, **meta):
        self._require()
        if not self.live:
            # Skeleton mode — pretend success but don't hit network
            logger.info(
                "[resend skeleton] would send email to=%s subj=%s "
                "(set RESEND_LIVE=1 to actually send)",
                to, subject,
            )
            return SendResult(
                success=True, provider=self.name,
                provider_reference="skeleton-no-send",
                raw_payload={"skeleton": True},
            )
        try:
            import requests  # type: ignore
            r = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": from_email or self.default_from,
                    "to": [to],
                    "subject": subject,
                    "html": body,
                },
                timeout=15,
            )
            if r.status_code in (200, 202):
                data = r.json()
                return SendResult(
                    success=True, provider=self.name,
                    provider_reference=data.get("id"),
                    raw_payload=data,
                )
            return SendResult(
                success=False, provider=self.name,
                error_message=f"HTTP {r.status_code}: {r.text[:300]}",
            )
        except Exception as e:
            logger.exception("Resend send failed")
            return SendResult(success=False, provider=self.name, error_message=str(e)[:500])

    def send_sms(self, to, body, **meta):
        raise NotImplementedError("Resend não envia SMS — use Zenvia.")

    def send_whatsapp(self, to, body, **meta):
        raise NotImplementedError("Resend não envia WhatsApp — use n8n.")


# ── Zenvia (sms) ──────────────────────────────────────────────────────────────

class ZenviaSmsProvider(NotificationProvider):
    """
    Skeleton for Zenvia SMS API (https://www.zenvia.com).

    Activates when ZENVIA_API_KEY is set. Endpoint:
        POST https://api.zenvia.com/v2/channels/sms/messages
        X-API-TOKEN: {ZENVIA_API_KEY}

    Same skeleton-vs-live protection: set ZENVIA_LIVE=1 to actually send.
    """

    name = "zenvia"

    def __init__(self, api_key: Optional[str] = None, default_from: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ZENVIA_API_KEY")
        self.default_from = default_from or os.environ.get("ZENVIA_FROM_ID", "automic")
        self.live = os.environ.get("ZENVIA_LIVE") == "1"

    def _require(self):
        if not self.api_key:
            raise RuntimeError("ZENVIA_API_KEY não configurado.")

    def send_sms(self, to, body, **meta):
        self._require()
        if not self.live:
            logger.info(
                "[zenvia skeleton] would send SMS to=%s "
                "(set ZENVIA_LIVE=1 to actually send)",
                to,
            )
            return SendResult(
                success=True, provider=self.name,
                provider_reference="skeleton-no-send",
                raw_payload={"skeleton": True},
            )
        try:
            import requests  # type: ignore
            r = requests.post(
                "https://api.zenvia.com/v2/channels/sms/messages",
                headers={
                    "X-API-TOKEN": self.api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "from": self.default_from,
                    "to": _normalize_phone(to),
                    "contents": [{"type": "text", "text": body}],
                },
                timeout=15,
            )
            if r.status_code in (200, 201):
                data = r.json()
                return SendResult(
                    success=True, provider=self.name,
                    provider_reference=data.get("id"),
                    raw_payload=data,
                )
            return SendResult(
                success=False, provider=self.name,
                error_message=f"HTTP {r.status_code}: {r.text[:300]}",
            )
        except Exception as e:
            logger.exception("Zenvia send failed")
            return SendResult(success=False, provider=self.name, error_message=str(e)[:500])

    def send_email(self, to, subject, body, from_email=None, **meta):
        raise NotImplementedError("Zenvia não envia email — use Resend.")

    def send_whatsapp(self, to, body, **meta):
        # Zenvia HAS WhatsApp API too, but we keep it separate to use n8n by default.
        raise NotImplementedError("Use N8nWhatsAppProvider para WhatsApp.")


# ── n8n (whatsapp via webhook) ────────────────────────────────────────────────

class N8nWhatsAppProvider(NotificationProvider):
    """
    Forwards WhatsApp sends to an n8n webhook the user controls.

    n8n then handles the actual WhatsApp Business / WPP send via whatever
    workflow the user built (Z-API, Whapi, baileys-on-VPS, etc).

    Activates when N8N_WEBHOOK_URL is set. Same live/skeleton split.
    """

    name = "n8n"

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.environ.get("N8N_WEBHOOK_URL")
        self.live = os.environ.get("N8N_LIVE") == "1"

    def _require(self):
        if not self.webhook_url:
            raise RuntimeError("N8N_WEBHOOK_URL não configurado.")

    def send_whatsapp(self, to, body, **meta):
        self._require()
        if not self.live:
            logger.info(
                "[n8n skeleton] would POST whatsapp to=%s url=%s "
                "(set N8N_LIVE=1 to actually send)",
                to, self.webhook_url,
            )
            return SendResult(
                success=True, provider=self.name,
                provider_reference="skeleton-no-send",
                raw_payload={"skeleton": True},
            )
        try:
            import requests  # type: ignore
            payload = {
                "to": _normalize_phone(to),
                "message": body,
                **{k: v for k, v in meta.items() if isinstance(v, (str, int, float, bool))},
            }
            r = requests.post(self.webhook_url, json=payload, timeout=15)
            if 200 <= r.status_code < 300:
                return SendResult(
                    success=True, provider=self.name,
                    raw_payload=_safe_json(r),
                )
            return SendResult(
                success=False, provider=self.name,
                error_message=f"HTTP {r.status_code}: {r.text[:300]}",
            )
        except Exception as e:
            logger.exception("n8n send failed")
            return SendResult(success=False, provider=self.name, error_message=str(e)[:500])

    def send_email(self, to, subject, body, from_email=None, **meta):
        raise NotImplementedError("n8n provider só envia WhatsApp.")

    def send_sms(self, to, body, **meta):
        raise NotImplementedError("n8n provider só envia WhatsApp.")


# ── Composite + Factory ───────────────────────────────────────────────────────

class CompositeNotificationProvider(NotificationProvider):
    """
    Routes each channel to the configured provider for that channel.

    Allows mixing: real Resend for email + mock for SMS while you set up Zenvia.
    """
    name = "composite"

    def __init__(
        self,
        email: NotificationProvider,
        sms: NotificationProvider,
        whatsapp: NotificationProvider,
    ):
        self.email = email
        self.sms = sms
        self.whatsapp = whatsapp

    def send_email(self, to, subject, body, from_email=None, **meta):
        return self.email.send_email(to, subject, body, from_email=from_email, **meta)

    def send_sms(self, to, body, **meta):
        return self.sms.send_sms(to, body, **meta)

    def send_whatsapp(self, to, body, **meta):
        return self.whatsapp.send_whatsapp(to, body, **meta)


_singleton: Optional[NotificationProvider] = None


def get_notification_provider() -> NotificationProvider:
    global _singleton
    if _singleton is not None:
        return _singleton

    # Email channel
    if os.environ.get("RESEND_API_KEY"):
        email_p: NotificationProvider = ResendEmailProvider()
    else:
        email_p = MockNotificationProvider()

    # SMS channel
    if os.environ.get("ZENVIA_API_KEY"):
        sms_p: NotificationProvider = ZenviaSmsProvider()
    else:
        sms_p = MockNotificationProvider()

    # WhatsApp channel
    if os.environ.get("N8N_WEBHOOK_URL"):
        wa_p: NotificationProvider = N8nWhatsAppProvider()
    else:
        wa_p = MockNotificationProvider()

    # If everything is mock, return ONE mock instance so tests can inspect a
    # single `.sent` list. Otherwise compose.
    all_mock = isinstance(email_p, MockNotificationProvider) and \
               isinstance(sms_p, MockNotificationProvider) and \
               isinstance(wa_p, MockNotificationProvider)
    if all_mock:
        # Reuse one instance across channels
        shared = MockNotificationProvider()
        _singleton = shared
    else:
        _singleton = CompositeNotificationProvider(email=email_p, sms=sms_p, whatsapp=wa_p)
    return _singleton


def reset_notification_provider() -> None:
    global _singleton
    _singleton = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_phone(phone: str) -> str:
    """Strip everything except digits + leading +."""
    if not phone:
        return phone
    s = phone.strip()
    if s.startswith("+"):
        return "+" + "".join(c for c in s[1:] if c.isdigit())
    return "".join(c for c in s if c.isdigit())


def _safe_json(response):
    try:
        return response.json()
    except Exception:
        return {"text": response.text[:300]}
