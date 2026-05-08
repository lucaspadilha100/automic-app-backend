"""Unit tests for Expansion 2 — observability + worker."""
import json
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

# Register full mapper graph (same trick as 1.8)
from tests.unit.test_expansion_1_8 import _Plan, _Tenant, _User  # noqa: F401

from app.core.logging_config import (
    JsonFormatter, PlainFormatter, configure_logging,
)
from app.core.middleware import (
    _ContextLogFilter, install_log_filter, get_request_id,
    set_tenant_context, set_user_context,
)
from app.core.sentry_setup import init_sentry, capture_tenant_context
from app.services.task_run_service import TaskRunService
from app.models.task_run import TaskRunStatus, TaskRunSource


# ── Logging formatters ────────────────────────────────────────────────────────

class TestJsonFormatter:
    def _record(self, msg="hello", level=logging.INFO, **extras):
        record = logging.LogRecord(
            name="automic.test", level=level, pathname=__file__, lineno=1,
            msg=msg, args=(), exc_info=None,
        )
        for k, v in extras.items():
            setattr(record, k, v)
        return record

    def test_emits_valid_json(self):
        line = JsonFormatter().format(self._record())
        data = json.loads(line)
        assert data["msg"] == "hello"
        assert data["level"] == "INFO"
        assert data["logger"] == "automic.test"
        assert "ts" in data

    def test_includes_structured_fields(self):
        rec = self._record(
            request_id="abc123", tenant_id="t-1", user_id="u-1",
            method="GET", path="/x", status_code=200, duration_ms=12.3,
        )
        data = json.loads(JsonFormatter().format(rec))
        assert data["request_id"] == "abc123"
        assert data["tenant_id"] == "t-1"
        assert data["user_id"] == "u-1"
        assert data["method"] == "GET"
        assert data["status_code"] == 200
        assert data["duration_ms"] == 12.3

    def test_handles_non_serializable_extras(self):
        rec = self._record()
        rec.weird = object()  # not JSON serializable
        # Must not raise
        line = JsonFormatter().format(rec)
        data = json.loads(line)
        assert "weird" in data


class TestPlainFormatter:
    def test_appends_extras_in_brackets(self):
        rec = logging.LogRecord(
            name="x", level=logging.INFO, pathname=__file__, lineno=1,
            msg="hi", args=(), exc_info=None,
        )
        rec.request_id = "rid-9"
        rec.status_code = 200
        out = PlainFormatter().format(rec)
        assert "request_id=rid-9" in out
        assert "status_code=200" in out


# ── Context filter / contextvars ──────────────────────────────────────────────

class TestContextFilter:
    def test_filter_injects_contextvars(self):
        flt = _ContextLogFilter()
        rec = logging.LogRecord(
            name="x", level=logging.INFO, pathname=__file__, lineno=1,
            msg="m", args=(), exc_info=None,
        )
        set_tenant_context("t-99")
        set_user_context("u-77")
        try:
            flt.filter(rec)
            assert rec.tenant_id == "t-99"
            assert rec.user_id == "u-77"
        finally:
            set_tenant_context(None)
            set_user_context(None)

    def test_filter_does_not_overwrite_explicit(self):
        flt = _ContextLogFilter()
        rec = logging.LogRecord(
            name="x", level=logging.INFO, pathname=__file__, lineno=1,
            msg="m", args=(), exc_info=None,
        )
        rec.tenant_id = "explicit"
        set_tenant_context("from-context")
        try:
            flt.filter(rec)
            assert rec.tenant_id == "explicit"  # not overwritten
        finally:
            set_tenant_context(None)


# ── Sentry wrapper (no-op when DSN unset) ─────────────────────────────────────

class TestSentrySetup:
    def setup_method(self):
        import os
        self._dsn = os.environ.pop("SENTRY_DSN", None)

    def teardown_method(self):
        import os
        if self._dsn:
            os.environ["SENTRY_DSN"] = self._dsn
        else:
            os.environ.pop("SENTRY_DSN", None)

    def test_init_no_dsn_returns_false(self):
        assert init_sentry() is False

    def test_capture_tenant_context_is_safe_when_disabled(self):
        # Must not raise even with no Sentry SDK / no DSN
        capture_tenant_context("tenant-1", "tenant-slug")


# ── TaskRun service ───────────────────────────────────────────────────────────

class TestTaskRunService:
    def setup_method(self):
        self.svc = TaskRunService()

    def test_start_creates_with_status_started(self):
        db = MagicMock()
        run = self.svc.start(db, "expire_trials", TaskRunSource.manual)
        assert run.task_name == "expire_trials"
        assert run.status == TaskRunStatus.started
        assert run.source == TaskRunSource.manual
        assert run.started_at is not None
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_finish_success_sets_duration(self):
        db = MagicMock()
        run = self.svc.start(db, "x")
        # Fast-forward by mocking finished_at math
        result = self.svc.finish_success(db, run, summary={"created": 5})
        assert result.status == TaskRunStatus.success
        assert result.finished_at is not None
        assert result.duration_ms is not None
        assert result.summary == {"created": 5}

    def test_finish_failed_captures_error(self):
        db = MagicMock()
        run = self.svc.start(db, "x")
        err = RuntimeError("boom")
        result = self.svc.finish_failed(db, run, err)
        assert result.status == TaskRunStatus.failed
        assert result.error_message == "boom"

    def test_record_context_success_path(self):
        db = MagicMock()
        with self.svc.record(db, "test_task") as ctx:
            ctx.set_summary({"hits": 3})
        # Two commits expected: one on start, one on finish_success
        assert db.commit.call_count >= 2

    def test_record_context_failure_path(self):
        db = MagicMock()
        with pytest.raises(ValueError):
            with self.svc.record(db, "test_task"):
                raise ValueError("nope")
        # Even on exception, finish_failed commits
        assert db.commit.call_count >= 2

    def test_summary_serializes_uuid_and_datetime(self):
        from app.services.task_run_service import _TaskRunContext
        run = MagicMock()
        ctx = _TaskRunContext(run)
        u = uuid4()
        dt = datetime(2026, 5, 8, 12, 0, 0, tzinfo=timezone.utc)
        ctx.set_summary({"id": u, "when": dt, "list": [u, "x"], "n": 5})
        assert ctx.summary["id"] == str(u)
        assert ctx.summary["when"] == dt.isoformat()
        assert ctx.summary["list"][0] == str(u)
        assert ctx.summary["list"][1] == "x"
        assert ctx.summary["n"] == 5
