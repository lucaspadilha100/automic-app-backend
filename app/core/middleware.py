"""
Request-context middleware.

For every HTTP request:
  1. Generate (or pick from header `X-Request-ID`) a request_id and
     attach it to request.state for downstream code.
  2. After the response, emit one structured 'access' log line with
     method, path, status_code, duration_ms, request_id.
  3. Propagate request_id back to the client via X-Request-ID response header.

Also provides a contextvar so `tenant_id` and `user_id` can be set
from auth middleware/deps and surfaced on every log line of that request
without being threaded through every function.
"""
from __future__ import annotations
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


_request_id_ctx: ContextVar[Optional[str]] = ContextVar("_request_id_ctx", default=None)
_tenant_id_ctx: ContextVar[Optional[str]] = ContextVar("_tenant_id_ctx", default=None)
_user_id_ctx: ContextVar[Optional[str]] = ContextVar("_user_id_ctx", default=None)


def get_request_id() -> Optional[str]:
    return _request_id_ctx.get()


def set_tenant_context(tenant_id: Optional[str]) -> None:
    _tenant_id_ctx.set(tenant_id)


def set_user_context(user_id: Optional[str]) -> None:
    _user_id_ctx.set(user_id)


class _ContextLogFilter(logging.Filter):
    """Pulls request_id, tenant_id, user_id from contextvars onto every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            rid = _request_id_ctx.get()
            if rid:
                record.request_id = rid
        if not getattr(record, "tenant_id", None):
            tid = _tenant_id_ctx.get()
            if tid:
                record.tenant_id = tid
        if not getattr(record, "user_id", None):
            uid = _user_id_ctx.get()
            if uid:
                record.user_id = uid
        return True


def install_log_filter() -> None:
    """Attach the context filter to the root logger. Idempotent."""
    root = logging.getLogger()
    if not any(isinstance(f, _ContextLogFilter) for f in root.filters):
        root.addFilter(_ContextLogFilter())


access_logger = logging.getLogger("automic.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Pick or generate request_id
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = _request_id_ctx.set(rid)
        # Reset tenant/user for fresh request — auth deps populate them later
        t_token = _tenant_id_ctx.set(None)
        u_token = _user_id_ctx.set(None)
        request.state.request_id = rid

        start = time.perf_counter()
        status_code = 500
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            # One access log line per request
            access_logger.info(
                "request",
                extra={
                    "request_id": rid,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "tenant_id": _tenant_id_ctx.get(),
                    "user_id": _user_id_ctx.get(),
                },
            )
            _request_id_ctx.reset(token)
            _tenant_id_ctx.reset(t_token)
            _user_id_ctx.reset(u_token)
