"""Small in-memory rate limiter for sensitive endpoints.

This is intentionally dependency-free and suitable for a single-process MVP/VPS.
For multi-worker production, replace with Redis/SlowAPI while keeping the same
call site in auth routes.
"""
from __future__ import annotations

from collections import defaultdict, deque
from time import time
from fastapi import Request

from app.core.config import settings
from app.core.exceptions import AppError

_login_attempts: dict[str, deque[float]] = defaultdict(deque)


def _client_key(request: Request, scope: str) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"
    return f"{scope}:{ip}"


def enforce_login_rate_limit(request: Request, scope: str = "login") -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return

    limit = max(int(settings.RATE_LIMIT_LOGIN_PER_MINUTE or 1), 1)
    window_seconds = 60
    now = time()
    key = _client_key(request, scope)
    attempts = _login_attempts[key]

    while attempts and now - attempts[0] > window_seconds:
        attempts.popleft()

    if len(attempts) >= limit:
        raise AppError(
            code="RATE_LIMIT_EXCEEDED",
            message="Muitas tentativas de login. Aguarde alguns instantes e tente novamente.",
            status_code=429,
        )

    attempts.append(now)
