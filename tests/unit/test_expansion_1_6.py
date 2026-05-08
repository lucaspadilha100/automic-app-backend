"""Unit tests for Expansion 1.6 services."""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.services.support_ticket_service import SupportTicketService
from app.services.owner_notification_service import OwnerNotificationService
from app.services.platform_document_service import PlatformDocumentService
from app.models.support_ticket import (
    SupportTicketStatus, SupportTicketCategory, SupportTicketPriority,
)
from app.models.owner_notification import (
    OwnerNotificationType, OwnerNotificationSeverity,
)
from app.models.platform_document import PlatformDocumentType
from app.schemas.support_ticket import (
    SupportTicketCreate, SupportTicketMessageCreate,
)
from app.schemas.platform_document import PlatformDocumentUpsert


# ── Support tickets ───────────────────────────────────────────────────────────

class TestSupportTicketService:
    def setup_method(self):
        self.svc = SupportTicketService()

    def _mock_db_creating(self):
        db = MagicMock()
        # When add() then flush() is called, just ignore — we don't run real DB
        # When tenant lookup happens, return None to skip the notification step
        db.query.return_value.filter.return_value.first.return_value = None
        return db

    def test_create_ticket_persists_subject_and_message(self):
        db = self._mock_db_creating()
        tenant_id = uuid4()
        user_id = uuid4()

        with patch("app.services.support_ticket_service.owner_notification_service"):
            ticket = self.svc.create_ticket(
                db, tenant_id=tenant_id, user_id=user_id,
                subject="  Bug no calendário  ",
                body="Quando clico fica em loading",
                category=SupportTicketCategory.bug,
                priority=SupportTicketPriority.high,
            )

        # subject is trimmed
        assert ticket.subject == "Bug no calendário"
        assert ticket.tenant_id == tenant_id
        assert ticket.created_by_user_id == user_id
        assert ticket.priority == SupportTicketPriority.high
        assert ticket.status == SupportTicketStatus.open

        # one ticket + one message added
        added = [c.args[0] for c in db.add.call_args_list]
        types_added = {type(o).__name__ for o in added}
        assert "SupportTicket" in types_added
        assert "SupportTicketMessage" in types_added


class TestSupportTicketStatusTransitions:
    def setup_method(self):
        self.svc = SupportTicketService()

    def test_tenant_reply_on_pending_reopens(self):
        db = MagicMock()
        ticket = MagicMock(
            status=SupportTicketStatus.pending,
            tenant_id=uuid4(),
            id=uuid4(),
            subject="x",
        )
        db.query.return_value.filter.return_value.first.return_value = None  # tenant lookup
        with patch("app.services.support_ticket_service.owner_notification_service"):
            self.svc.add_message(
                db, ticket=ticket,
                author_user_id=uuid4(), author_side="tenant",
                body="oi de novo",
            )
        assert ticket.status == SupportTicketStatus.open

    def test_automic_reply_on_open_moves_to_pending(self):
        db = MagicMock()
        ticket = MagicMock(
            status=SupportTicketStatus.open,
            tenant_id=uuid4(),
            id=uuid4(),
            subject="x",
        )
        with patch("app.services.support_ticket_service.owner_notification_service"):
            self.svc.add_message(
                db, ticket=ticket,
                author_user_id=uuid4(), author_side="automic",
                body="ok, vamos olhar",
            )
        assert ticket.status == SupportTicketStatus.pending

    def test_closed_ticket_rejects_messages(self):
        from app.core.exceptions import ForbiddenError
        db = MagicMock()
        ticket = MagicMock(status=SupportTicketStatus.closed, id=uuid4())
        with pytest.raises(ForbiddenError):
            self.svc.add_message(
                db, ticket=ticket, author_user_id=uuid4(),
                author_side="tenant", body="reabre",
            )

    def test_tenant_reply_on_resolved_reopens_and_clears_resolved_at(self):
        db = MagicMock()
        ticket = MagicMock(
            status=SupportTicketStatus.resolved,
            tenant_id=uuid4(),
            id=uuid4(),
            subject="x",
            resolved_at="2026-05-01T00:00:00Z",
        )
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("app.services.support_ticket_service.owner_notification_service"):
            self.svc.add_message(
                db, ticket=ticket,
                author_user_id=uuid4(), author_side="tenant",
                body="voltou",
            )
        assert ticket.status == SupportTicketStatus.open
        assert ticket.resolved_at is None


class TestSupportTicketSchemas:
    def test_subject_must_not_be_empty(self):
        with pytest.raises(ValidationError):
            SupportTicketCreate(subject="", body="bla")

    def test_message_body_required(self):
        with pytest.raises(ValidationError):
            SupportTicketMessageCreate(body="")

    def test_defaults(self):
        m = SupportTicketCreate(subject="Q", body="B")
        assert m.category == SupportTicketCategory.question
        assert m.priority == SupportTicketPriority.normal


# ── Owner notifications ───────────────────────────────────────────────────────

class TestOwnerNotificationService:
    def setup_method(self):
        self.svc = OwnerNotificationService()

    def test_emit_returns_none_on_failure(self):
        db = MagicMock()
        db.add.side_effect = RuntimeError("boom")
        # Must not raise — emit always swallows errors
        result = self.svc.emit(
            db,
            notification_type=OwnerNotificationType.tenant_signup,
            title="X",
        )
        assert result is None

    def test_emit_tenant_signup_uses_success_severity(self):
        db = MagicMock()
        with patch.object(self.svc, "emit") as emit_mock:
            self.svc.emit_tenant_signup(db, uuid4(), "Tenant X")
        kwargs = emit_mock.call_args.kwargs
        assert kwargs["severity"] == OwnerNotificationSeverity.success
        assert kwargs["notification_type"] == OwnerNotificationType.tenant_signup

    def test_emit_status_change_maps_to_correct_type(self):
        db = MagicMock()
        with patch.object(self.svc, "emit") as emit_mock:
            self.svc.emit_tenant_status_change(
                db, uuid4(), "T", "active", "cancelled",
            )
        kwargs = emit_mock.call_args.kwargs
        assert kwargs["notification_type"] == OwnerNotificationType.tenant_cancelled
        assert kwargs["severity"] == OwnerNotificationSeverity.error

    def test_emit_status_change_unknown_status_uses_custom(self):
        db = MagicMock()
        with patch.object(self.svc, "emit") as emit_mock:
            self.svc.emit_tenant_status_change(
                db, uuid4(), "T", "active", "frozen",
            )
        kwargs = emit_mock.call_args.kwargs
        assert kwargs["notification_type"] == OwnerNotificationType.custom

    def test_emit_support_ticket_priority_drives_severity(self):
        db = MagicMock()
        with patch.object(self.svc, "emit") as emit_mock:
            self.svc.emit_support_ticket_created(
                db, uuid4(), uuid4(), "T", "Crash", "urgent",
            )
        assert emit_mock.call_args.kwargs["severity"] == OwnerNotificationSeverity.error

        with patch.object(self.svc, "emit") as emit_mock:
            self.svc.emit_support_ticket_created(
                db, uuid4(), uuid4(), "T", "doubt", "normal",
            )
        assert emit_mock.call_args.kwargs["severity"] == OwnerNotificationSeverity.info


# ── Platform documents ────────────────────────────────────────────────────────

class TestPlatformDocumentService:
    def setup_method(self):
        self.svc = PlatformDocumentService()

    def test_get_or_404_raises_when_missing(self):
        from app.core.exceptions import NotFoundError
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(NotFoundError):
            self.svc.get_or_404(db, PlatformDocumentType.terms_of_service)

    def test_upsert_creates_on_first_call(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        result = self.svc.upsert(
            db, PlatformDocumentType.privacy_policy,
            title="Privacidade", content="Nós...", version="1.0",
        )
        db.add.assert_called()
        db.commit.assert_called()
        assert result.title == "Privacidade"
        assert result.version == "1.0"
        assert result.revision_count == 1

    def test_upsert_increments_revision_on_existing(self):
        db = MagicMock()
        existing = MagicMock(
            document_type=PlatformDocumentType.terms_of_service,
            title="ToS v1", content="old", version="1.0", revision_count=2,
        )
        db.query.return_value.filter.return_value.first.return_value = existing

        self.svc.upsert(
            db, PlatformDocumentType.terms_of_service,
            title="ToS v2", content="new", version="2.0",
        )
        assert existing.title == "ToS v2"
        assert existing.content == "new"
        assert existing.version == "2.0"
        assert existing.revision_count == 3


class TestPlatformDocumentSchemas:
    def test_rejects_empty_title(self):
        with pytest.raises(ValidationError):
            PlatformDocumentUpsert(title="", content="x")

    def test_rejects_empty_content(self):
        with pytest.raises(ValidationError):
            PlatformDocumentUpsert(title="x", content="")

    def test_default_version(self):
        m = PlatformDocumentUpsert(title="ToS", content="...")
        assert m.version == "1.0"
