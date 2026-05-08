"""Unit tests for Expansion 1.7 — onboarding + trial + health."""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.onboarding import TenantSignupRequest
from app.services.onboarding_service import OnboardingService
from app.services.tenant_ops_service import TenantOpsService
from app.core.exceptions import ConflictError, NotFoundError


# ── Schema validation ─────────────────────────────────────────────────────────

class TestTenantSignupRequestSchema:
    def _valid_payload(self, **overrides):
        base = dict(
            company_name="Studio Beleza",
            slug="studio-beleza",
            owner_name="Maria",
            owner_email="maria@studio.com",
            owner_password="Senha@1234",
            accept_terms=True,
        )
        base.update(overrides)
        return base

    def test_happy_path(self):
        m = TenantSignupRequest(**self._valid_payload())
        assert m.slug == "studio-beleza"
        assert m.accept_terms is True

    def test_lowercases_slug(self):
        m = TenantSignupRequest(**self._valid_payload(slug="Studio-Beleza"))
        assert m.slug == "studio-beleza"

    def test_rejects_uppercase_in_slug(self):
        # After lowercase normalization, uppercase still rejected if user
        # passed a single-letter or uppercase-only slug. We validate after
        # lowercasing, so this only fails when the resulting slug breaks regex.
        # Use a clearly invalid character to test rejection:
        with pytest.raises(ValidationError):
            TenantSignupRequest(**self._valid_payload(slug="bad slug"))

    def test_rejects_starts_with_hyphen(self):
        with pytest.raises(ValidationError):
            TenantSignupRequest(**self._valid_payload(slug="-bad"))

    def test_rejects_consecutive_hyphens(self):
        with pytest.raises(ValidationError):
            TenantSignupRequest(**self._valid_payload(slug="a--b"))

    def test_rejects_too_short_slug(self):
        with pytest.raises(ValidationError):
            TenantSignupRequest(**self._valid_payload(slug="ab"))

    def test_rejects_reserved_slug(self):
        with pytest.raises(ValidationError):
            TenantSignupRequest(**self._valid_payload(slug="admin"))
        with pytest.raises(ValidationError):
            TenantSignupRequest(**self._valid_payload(slug="master"))
        with pytest.raises(ValidationError):
            TenantSignupRequest(**self._valid_payload(slug="automic"))

    def test_rejects_when_terms_not_accepted(self):
        with pytest.raises(ValidationError):
            TenantSignupRequest(**self._valid_payload(accept_terms=False))

    def test_rejects_short_password(self):
        with pytest.raises(ValidationError):
            TenantSignupRequest(**self._valid_payload(owner_password="123"))

    def test_rejects_invalid_email(self):
        with pytest.raises(ValidationError):
            TenantSignupRequest(**self._valid_payload(owner_email="not-an-email"))

    def test_rejects_empty_name(self):
        with pytest.raises(ValidationError):
            TenantSignupRequest(**self._valid_payload(company_name="   "))


# ── Onboarding service ────────────────────────────────────────────────────────

class TestOnboardingService:
    def setup_method(self):
        self.svc = OnboardingService()

    def _mock_db(self, slug_taken=False, email_taken=False, plan_exists=True):
        """Build a MagicMock DB with controllable behavior."""
        db = MagicMock()

        def query_side_effect(model):
            from app.models.tenant import Tenant
            from app.models.user import User
            from app.models.plan import Plan
            from app.models.platform_document import PlatformDocument

            q = MagicMock()
            if model is Tenant:
                # Slug uniqueness check
                q.filter.return_value.first.return_value = MagicMock() if slug_taken else None
            elif model is User:
                q.filter.return_value.first.return_value = MagicMock() if email_taken else None
            elif model is Plan:
                if plan_exists:
                    plan = MagicMock(id=uuid4(), name="Starter")
                    q.filter.return_value.order_by.return_value.first.return_value = plan
                else:
                    q.filter.return_value.order_by.return_value.first.return_value = None
            elif model is PlatformDocument:
                # No ToS document published
                q.filter.return_value.first.return_value = None
            else:
                q.filter.return_value.first.return_value = None
            return q

        db.query.side_effect = query_side_effect
        return db

    def test_rejects_taken_slug(self):
        db = self._mock_db(slug_taken=True)
        with patch("app.services.onboarding_service.unit_service"), \
             patch("app.services.onboarding_service.owner_notification_service"):
            with pytest.raises(ConflictError) as exc_info:
                self.svc.signup_tenant(
                    db, "Studio", "studio", "Maria",
                    "m@x.com", "secret123",
                )
            assert "já está em uso" in exc_info.value.message

    def test_rejects_taken_email(self):
        db = self._mock_db(email_taken=True)
        with patch("app.services.onboarding_service.unit_service"), \
             patch("app.services.onboarding_service.owner_notification_service"):
            with pytest.raises(ConflictError) as exc_info:
                self.svc.signup_tenant(
                    db, "Studio", "studio", "Maria",
                    "m@x.com", "secret123",
                )
            assert "email" in exc_info.value.message.lower()

    def test_rejects_when_no_starter_plan(self):
        db = self._mock_db(plan_exists=False)
        with patch("app.services.onboarding_service.unit_service"), \
             patch("app.services.onboarding_service.owner_notification_service"):
            with pytest.raises(NotFoundError) as exc_info:
                self.svc.signup_tenant(
                    db, "Studio", "studio", "Maria",
                    "m@x.com", "secret123",
                )
            assert "Starter" in exc_info.value.message

    def test_lowercases_slug_and_email(self):
        db = self._mock_db()
        with patch("app.services.onboarding_service.unit_service") as unit_mock, \
             patch("app.services.onboarding_service.owner_notification_service"):
            tenant, user, sub, ver = self.svc.signup_tenant(
                db, "Studio", "Studio-X", "Maria",
                "Maria@X.COM", "secret123",
            )
        # Tenant created with normalized slug
        assert tenant.slug == "studio-x"
        # User created with normalized email
        assert user.email == "maria@x.com"
        # Should have ensured a main unit
        unit_mock.ensure_main_unit.assert_called_once()
        # Subscription captured signup source
        assert sub.signup_source == "self_service"


# ── Trial expiration ──────────────────────────────────────────────────────────

class TestTrialExpiration:
    def setup_method(self):
        self.svc = TenantOpsService()

    def test_expire_trials_with_no_matches_returns_zero(self):
        db = MagicMock()
        db.query.return_value.join.return_value.filter.return_value.all.return_value = []
        result = self.svc.expire_trials(db)
        assert result["suspended_count"] == 0
        # No commit needed when nothing changes
        db.commit.assert_not_called()

    def test_expire_trials_suspends_matched_tenants(self):
        db = MagicMock()
        tenant = MagicMock(
            id=uuid4(), name="Studio Vencido", status="trial", deleted_at=None,
        )
        sub = MagicMock(status="trial", trial_ends_at=datetime.now(timezone.utc) - timedelta(days=2))
        db.query.return_value.join.return_value.filter.return_value.all.return_value = [
            (tenant, sub),
        ]

        with patch("app.services.tenant_ops_service.owner_notification_service") as notif_mock:
            result = self.svc.expire_trials(db)

        assert tenant.status == "suspended"
        assert sub.status == "past_due"
        assert result["suspended_count"] == 1
        notif_mock.emit_tenant_status_change.assert_called_once()
        db.commit.assert_called_once()


# ── Risk classification ───────────────────────────────────────────────────────

class TestRiskClassification:
    def setup_method(self):
        self.svc = TenantOpsService()
        self.now = datetime.now(timezone.utc)
        self.seven_ago = self.now - timedelta(days=7)
        self.thirty_ago = self.now - timedelta(days=30)

    def _classify(self, **kwargs):
        return self.svc._classify_risk(
            tenant_status=kwargs.get("tenant_status", "trial"),
            subscription_status=kwargs.get("subscription_status", "trial"),
            last_login_at=kwargs.get("last_login_at"),
            last_appointment_at=kwargs.get("last_appointment_at"),
            appts_30=kwargs.get("appts_30", 0),
            days_to_trial_end=kwargs.get("days_to_trial_end"),
            seven_days_ago=self.seven_ago,
            thirty_days_ago=self.thirty_ago,
        )

    def test_suspended_tenant_is_critical(self):
        assert self._classify(tenant_status="suspended") == "critical"

    def test_cancelled_subscription_is_critical(self):
        assert self._classify(subscription_status="cancelled") == "critical"

    def test_trial_about_to_expire_is_high(self):
        assert self._classify(days_to_trial_end=2) == "high"
        assert self._classify(days_to_trial_end=0) == "high"

    def test_no_activity_30_days_is_high(self):
        old = self.now - timedelta(days=45)
        assert self._classify(
            tenant_status="active",
            subscription_status="active",
            last_login_at=old, last_appointment_at=old,
        ) == "high"

    def test_activity_in_last_7_days_is_low(self):
        recent = self.now - timedelta(days=2)
        assert self._classify(
            tenant_status="active",
            subscription_status="active",
            last_login_at=recent,
        ) == "low"

    def test_activity_8_to_30_days_ago_is_medium(self):
        mid = self.now - timedelta(days=15)
        assert self._classify(
            tenant_status="active",
            subscription_status="active",
            last_login_at=mid,
        ) == "medium"
