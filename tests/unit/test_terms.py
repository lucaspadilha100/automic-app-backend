"""Unit tests for the Terms and Consents module."""
import uuid
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.main import app
from app.models.term import TenantTerm, CustomerTermAcceptance, TermType
from app.services.term_service import TermService


# ---- Model field tests ----

def test_tenant_term_model_fields():
    assert TenantTerm.__tablename__ == "tenant_terms"
    assert hasattr(TenantTerm, "id")
    assert hasattr(TenantTerm, "tenant_id")
    assert hasattr(TenantTerm, "title")
    assert hasattr(TenantTerm, "content")
    assert hasattr(TenantTerm, "term_type")
    assert hasattr(TenantTerm, "version")
    assert hasattr(TenantTerm, "is_active")
    assert hasattr(TenantTerm, "created_at")
    assert hasattr(TenantTerm, "updated_at")


def test_customer_term_acceptance_model_fields():
    assert CustomerTermAcceptance.__tablename__ == "customer_term_acceptances"
    assert hasattr(CustomerTermAcceptance, "id")
    assert hasattr(CustomerTermAcceptance, "tenant_id")
    assert hasattr(CustomerTermAcceptance, "customer_account_id")
    assert hasattr(CustomerTermAcceptance, "tenant_customer_id")
    assert hasattr(CustomerTermAcceptance, "term_id")
    assert hasattr(CustomerTermAcceptance, "accepted_at")
    assert hasattr(CustomerTermAcceptance, "ip_address")
    assert hasattr(CustomerTermAcceptance, "user_agent")
    assert hasattr(CustomerTermAcceptance, "created_at")


def test_term_type_enum_values():
    assert TermType.general == "general"
    assert TermType.procedure == "procedure"
    assert TermType.image_authorization == "image_authorization"
    assert TermType.privacy_policy == "privacy_policy"
    assert TermType.post_procedure == "post_procedure"


# ---- Route registration tests ----

def test_admin_terms_routes_registered():
    routes = {
        (route.path, method)
        for route in app.routes
        if hasattr(route, "methods")
        for method in route.methods
    }
    expected = {
        ("/api/v1/admin/terms", "GET"),
        ("/api/v1/admin/terms", "POST"),
        ("/api/v1/admin/terms/{term_id}", "GET"),
        ("/api/v1/admin/terms/{term_id}", "PUT"),
        ("/api/v1/admin/terms/{term_id}/status", "PATCH"),
    }
    missing = expected - routes
    assert not missing, f"Missing routes: {missing}"


def test_customer_terms_routes_registered():
    routes = {
        (route.path, method)
        for route in app.routes
        if hasattr(route, "methods")
        for method in route.methods
    }
    expected = {
        ("/api/v1/customer/tenants/{slug}/terms", "GET"),
        ("/api/v1/customer/tenants/{slug}/terms/{term_id}/accept", "POST"),
    }
    missing = expected - routes
    assert not missing, f"Missing routes: {missing}"


# ---- Service unit tests ----

def _mock_db():
    return MagicMock()


def _make_term(tenant_id=None, is_active=True):
    term = MagicMock(spec=TenantTerm)
    term.id = uuid.uuid4()
    term.tenant_id = tenant_id or uuid.uuid4()
    term.title = "Termo Geral"
    term.content = "Conteúdo do termo."
    term.term_type = TermType.general
    term.version = "1.0"
    term.is_active = is_active
    return term


def test_list_terms_filters_by_tenant():
    svc = TermService()
    db = _mock_db()
    tenant_id = uuid.uuid4()

    mock_query = db.query.return_value
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.all.return_value = []

    result = svc.list_terms(db=db, tenant_id=tenant_id)
    assert result == []
    db.query.assert_called_once_with(TenantTerm)


def test_list_active_terms_for_customer():
    svc = TermService()
    db = _mock_db()
    tenant_id = uuid.uuid4()
    active_term = _make_term(tenant_id=tenant_id, is_active=True)

    mock_query = db.query.return_value
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.all.return_value = [active_term]

    result = svc.list_active_terms_for_customer(db=db, tenant_id=tenant_id)
    assert len(result) == 1
    assert result[0].is_active is True


def test_accept_term_blocks_wrong_tenant():
    from app.core.exceptions import ForbiddenError
    svc = TermService()
    db = _mock_db()

    tenant_id = uuid.uuid4()
    other_tenant_id = uuid.uuid4()
    term = _make_term(tenant_id=other_tenant_id, is_active=True)

    mock_query = db.query.return_value
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = term

    with pytest.raises(ForbiddenError):
        svc.accept_term(
            db=db,
            tenant_id=tenant_id,
            term_id=term.id,
            customer_account_id=uuid.uuid4(),
        )


def test_accept_term_blocks_inactive_term():
    from app.core.exceptions import ForbiddenError
    svc = TermService()
    db = _mock_db()

    tenant_id = uuid.uuid4()
    term = _make_term(tenant_id=tenant_id, is_active=False)

    mock_query = db.query.return_value
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = term

    with pytest.raises(ForbiddenError):
        svc.accept_term(
            db=db,
            tenant_id=tenant_id,
            term_id=term.id,
            customer_account_id=uuid.uuid4(),
        )


def test_accept_term_emits_customer_event():
    """Verify customer_event_service.emit is called on accept."""
    svc = TermService()
    db = _mock_db()
    tenant_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    term = _make_term(tenant_id=tenant_id, is_active=True)

    # Set up db queries: first returns the term, second returns None (no tenant_customer)
    call_count = [0]

    def query_side_effect(model):
        mock_q = MagicMock()
        mock_q.filter.return_value = mock_q
        if call_count[0] == 0:
            mock_q.first.return_value = term
        else:
            mock_q.first.return_value = None
        call_count[0] += 1
        return mock_q

    db.query.side_effect = query_side_effect

    with patch("app.services.term_service.customer_event_service") as mock_event_svc, \
         patch("app.services.term_service.audit_service"):
        mock_event_svc.emit.return_value = MagicMock()

        # Mock the acceptance creation
        acceptance = MagicMock(spec=CustomerTermAcceptance)
        acceptance.id = uuid.uuid4()
        acceptance.term_id = term.id
        acceptance.term = term
        acceptance.accepted_at = datetime.now(timezone.utc)

        db.add.return_value = None
        db.flush.return_value = None
        db.commit.return_value = None
        db.refresh.side_effect = lambda obj: None

        try:
            svc.accept_term(
                db=db,
                tenant_id=tenant_id,
                term_id=term.id,
                customer_account_id=customer_id,
                ip_address="127.0.0.1",
                user_agent="test-agent",
            )
        except Exception:
            pass  # db.refresh may fail on mock

        mock_event_svc.emit.assert_called_once()
        call_kwargs = mock_event_svc.emit.call_args
        assert call_kwargs.kwargs.get("event_type") == "term_accepted"
        assert call_kwargs.kwargs.get("tenant_id") == tenant_id


def test_create_term_calls_audit_log():
    """Verify audit_service.log is called on create."""
    svc = TermService()
    db = _mock_db()
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    with patch("app.services.term_service.audit_service") as mock_audit:
        mock_audit.log.return_value = MagicMock()
        db.flush.return_value = None
        db.commit.return_value = None

        # Mock the term being created
        created_term = _make_term(tenant_id=tenant_id)
        db.add.return_value = None
        db.refresh.side_effect = lambda obj: None

        try:
            svc.create_term(
                db=db,
                tenant_id=tenant_id,
                data={
                    "title": "Termo Geral",
                    "content": "Conteúdo.",
                    "term_type": TermType.general,
                    "version": "1.0",
                    "is_active": True,
                },
                user_id=user_id,
            )
        except Exception:
            pass  # db.refresh may fail on mock

        mock_audit.log.assert_called_once()
        call_kwargs = mock_audit.log.call_args.kwargs
        assert call_kwargs.get("action") == "term_created"
        assert call_kwargs.get("tenant_id") == tenant_id


def test_set_term_status_calls_audit_log():
    """Verify audit_service.log is called on status change."""
    from app.core.exceptions import NotFoundError
    svc = TermService()
    db = _mock_db()
    tenant_id = uuid.uuid4()
    term = _make_term(tenant_id=tenant_id, is_active=True)

    mock_q = MagicMock()
    mock_q.filter.return_value = mock_q
    mock_q.first.return_value = term
    db.query.return_value = mock_q

    with patch("app.services.term_service.audit_service") as mock_audit:
        mock_audit.log.return_value = MagicMock()

        svc.set_term_status(
            db=db,
            tenant_id=tenant_id,
            term_id=term.id,
            is_active=False,
        )

        mock_audit.log.assert_called_once()
        call_kwargs = mock_audit.log.call_args.kwargs
        assert "deactivated" in call_kwargs.get("action", "")
