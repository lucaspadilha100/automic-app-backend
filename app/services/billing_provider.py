"""
Abstraction over billing providers for tenant SaaS subscription invoices.

The abstraction lets us:
  - run end-to-end with `MockBillingProvider` (no external account required)
  - swap to a real provider (Mercado Pago) by setting BILLING_PROVIDER=mercadopago
    and the provider's API key in the env

The MercadoPago implementation is a *skeleton* — real HTTP calls are
behind an env-toggled stub. When the user creates an MP account and sets
MERCADOPAGO_ACCESS_TOKEN in the env, the stub turns into real calls.

This file defines:
  - BillingProvider (abstract)
  - MockBillingProvider (default — generates fake QR/link, accepts manual mark-paid)
  - MercadoPagoBillingProvider (skeleton; raises NotImplementedError unless wired)
  - get_billing_provider() factory that reads settings.BILLING_PROVIDER
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional
from dataclasses import dataclass
import os
import uuid


@dataclass
class ChargeResult:
    payment_provider: str
    payment_method: str
    payment_qr_code: Optional[str] = None
    payment_link: Optional[str] = None
    expires_at: Optional[datetime] = None
    provider_reference: Optional[str] = None
    raw_payload: Optional[dict] = None


class BillingProvider:
    """Abstract billing provider for tenant subscription charges."""

    name = "abstract"

    def create_charge(
        self,
        invoice_id: uuid.UUID,
        amount: float,
        currency: str,
        method: str,
        tenant_name: str,
    ) -> ChargeResult:
        raise NotImplementedError

    def verify_webhook_signature(self, body: bytes, signature_header: str) -> bool:
        """Return True if the webhook came from the legitimate provider."""
        raise NotImplementedError


class MockBillingProvider(BillingProvider):
    """
    Default billing provider for development and CI.

    `create_charge` returns a fake QR/link that the master can manually
    mark as paid through `POST /master/invoices/{id}/mark-paid`.

    No external HTTP, no account, no fees. Real webhooks are tested by
    POSTing to /webhooks/billing/mock.
    """
    name = "mock"

    def create_charge(
        self,
        invoice_id: uuid.UUID,
        amount: float,
        currency: str,
        method: str,
        tenant_name: str,
    ) -> ChargeResult:
        ref = f"mock_{uuid.uuid4().hex[:12]}"
        # 30-min expiration is realistic for Pix QR flows
        expires = datetime.now(timezone.utc) + timedelta(minutes=30)
        if method == "pix":
            qr = (
                f"00020126360014BR.GOV.BCB.PIX0114MOCK{ref[:18]}"
                f"5204000053039865802BR5913{tenant_name[:24].upper().ljust(24)}"
                f"6304ABCD"
            )
            return ChargeResult(
                payment_provider=self.name, payment_method="pix",
                payment_qr_code=qr, expires_at=expires,
                provider_reference=ref,
                raw_payload={"mock": True, "amount": amount, "currency": currency},
            )
        # default to a fake checkout link
        return ChargeResult(
            payment_provider=self.name, payment_method=method,
            payment_link=f"https://mock.automic.tech/checkout/{ref}",
            expires_at=expires, provider_reference=ref,
            raw_payload={"mock": True, "amount": amount, "currency": currency},
        )

    def verify_webhook_signature(self, body: bytes, signature_header: str) -> bool:
        # Mock provider accepts any signature in dev. In prod we never run mock.
        return True


class MercadoPagoBillingProvider(BillingProvider):
    """
    Skeleton for the real Mercado Pago integration.

    Activates only when the env has MERCADOPAGO_ACCESS_TOKEN set and
    BILLING_PROVIDER=mercadopago. Otherwise, attempting to call any method
    raises a clear runtime error so we don't silently fall back to nothing.
    """
    name = "mercadopago"

    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or os.environ.get("MERCADOPAGO_ACCESS_TOKEN")

    def _require_token(self):
        if not self.access_token:
            raise RuntimeError(
                "MERCADOPAGO_ACCESS_TOKEN não configurado. "
                "Defina BILLING_PROVIDER=mock ou configure o token do MP."
            )

    def create_charge(
        self,
        invoice_id: uuid.UUID,
        amount: float,
        currency: str,
        method: str,
        tenant_name: str,
    ) -> ChargeResult:
        self._require_token()
        # When wiring for real:
        #   import requests
        #   r = requests.post(
        #     "https://api.mercadopago.com/v1/payments",
        #     headers={"Authorization": f"Bearer {self.access_token}"},
        #     json={"transaction_amount": amount, "payment_method_id": method,
        #           "description": f"AUTOMIC {tenant_name}", ... },
        #     timeout=15,
        #   )
        # For now, we explicitly fail if someone tries to use this without a real token.
        raise NotImplementedError(
            "Integração real com Mercado Pago será ativada quando o MP for configurado."
        )

    def verify_webhook_signature(self, body: bytes, signature_header: str) -> bool:
        self._require_token()
        raise NotImplementedError


_provider_singleton: Optional[BillingProvider] = None


def get_billing_provider() -> BillingProvider:
    """Return the configured billing provider instance (cached singleton)."""
    global _provider_singleton
    if _provider_singleton is not None:
        return _provider_singleton
    name = os.environ.get("BILLING_PROVIDER", "mock").lower()
    if name == "mercadopago":
        _provider_singleton = MercadoPagoBillingProvider()
    else:
        _provider_singleton = MockBillingProvider()
    return _provider_singleton


def reset_billing_provider() -> None:
    """For tests — drop the cached singleton so the env can be re-read."""
    global _provider_singleton
    _provider_singleton = None
