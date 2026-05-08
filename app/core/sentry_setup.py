"""
Sentry initialization wrapper.

Activates only when both:
  - SENTRY_DSN env var is set
  - sentry-sdk is installed

Otherwise it is a no-op — the app keeps working with zero changes. This lets
us deploy without forcing the user to create a Sentry account.

When you're ready to use Sentry:
  1. `pip install sentry-sdk[fastapi]`
  2. Set `SENTRY_DSN=https://xxxx@xxxx.ingest.sentry.io/yyy`
  3. Optionally `SENTRY_ENVIRONMENT=production` and `SENTRY_TRACES_SAMPLE_RATE=0.1`
"""
from __future__ import annotations
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def init_sentry() -> bool:
    """
    Initialize Sentry. Returns True if active, False otherwise.

    Idempotent: calling twice is safe — the SDK ignores re-init.
    """
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        logger.debug("SENTRY_DSN not set — Sentry disabled.")
        return False

    try:
        import sentry_sdk  # type: ignore
        from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration  # type: ignore
    except ImportError:
        logger.warning(
            "SENTRY_DSN is set but sentry-sdk is not installed. "
            "Run: pip install 'sentry-sdk[fastapi]'",
        )
        return False

    environment = os.environ.get("SENTRY_ENVIRONMENT") or os.environ.get("ENVIRONMENT", "development")
    try:
        sample = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.0"))
    except (TypeError, ValueError):
        sample = 0.0

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=sample,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        # Send PII conservatively — we'll add tags for tenant/user explicitly
        send_default_pii=False,
    )
    logger.info("Sentry initialized (env=%s, sample=%.2f).", environment, sample)
    return True


def capture_tenant_context(tenant_id: Optional[str], tenant_slug: Optional[str] = None) -> None:
    """Tag the current Sentry scope with the tenant. No-op if Sentry disabled."""
    try:
        import sentry_sdk  # type: ignore
        sentry_sdk.set_tag("tenant_id", tenant_id or "")
        if tenant_slug:
            sentry_sdk.set_tag("tenant_slug", tenant_slug)
    except ImportError:
        pass
    except Exception:  # never break callers
        pass
