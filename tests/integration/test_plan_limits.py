"""
Testes das regras de limite de plano e feature flags.
"""
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.plan_limit_service import PlanLimitService
from app.services.feature_flag_service import FeatureFlagService
from app.core.exceptions import (
    ServiceLimitReachedError, ProfessionalLimitReachedError,
    UserLimitReachedError, PackageLimitReachedError,
    UnitLimitReachedError, FeatureDisabledError,
)


def make_tenant():
    t = MagicMock()
    t.id = uuid4()
    return t


def make_plan(**kwargs):
    plan = MagicMock()
    plan.max_services = kwargs.get("max_services", None)
    plan.max_professionals = kwargs.get("max_professionals", None)
    plan.max_users = kwargs.get("max_users", None)
    plan.max_appointments_per_month = kwargs.get("max_appointments_per_month", None)
    plan.max_units = kwargs.get("max_units", 1)
    plan.max_packages = kwargs.get("max_packages", None)
    for k, v in kwargs.items():
        setattr(plan, k, v)
    return plan


class TestPlanLimitService:
    def setup_method(self):
        self.svc = PlanLimitService()

    def _mock_db(self, plan, override=None, count=0):
        db = MagicMock()
        sub = MagicMock()
        sub.plan_id = uuid4()

        # sub query
        sub_q = MagicMock()
        sub_q.order_by.return_value.first.return_value = sub

        # plan query
        plan_q = MagicMock()
        plan_q.filter.return_value.first.return_value = plan

        # override query
        ovr_q = MagicMock()
        ovr_q.filter.return_value.first.return_value = override

        # count query
        count_q = MagicMock()
        count_q.filter.return_value.count.return_value = count

        def query_side_effect(model):
            from app.models.tenant import TenantSubscription, TenantLimitOverride
            from app.models.plan import Plan
            from app.models.service import Service
            from app.models.professional import Professional
            from app.models.user import User
            from app.models.package import Package
            from app.models.unit import Unit

            if model is TenantSubscription:
                return sub_q
            elif model is Plan:
                return plan_q
            elif model is TenantLimitOverride:
                return ovr_q
            else:
                return count_q

        db.query.side_effect = query_side_effect
        return db

    def test_service_limit_unlimited(self):
        """Plano sem limite não levanta erro."""
        plan = make_plan(max_services=None)
        db = self._mock_db(plan, count=9999)
        tenant = make_tenant()
        # Should not raise
        self.svc.check_service_limit(db, tenant)

    def test_service_limit_reached(self):
        plan = make_plan(max_services=5)
        db = self._mock_db(plan, count=5)
        tenant = make_tenant()
        with pytest.raises(ServiceLimitReachedError):
            self.svc.check_service_limit(db, tenant)

    def test_service_limit_not_reached(self):
        plan = make_plan(max_services=10)
        db = self._mock_db(plan, count=4)
        tenant = make_tenant()
        # Should not raise
        self.svc.check_service_limit(db, tenant)

    def test_professional_limit_reached(self):
        plan = make_plan(max_professionals=2)
        db = self._mock_db(plan, count=2)
        tenant = make_tenant()
        with pytest.raises(ProfessionalLimitReachedError):
            self.svc.check_professional_limit(db, tenant)

    def test_user_limit_reached(self):
        plan = make_plan(max_users=3)
        db = self._mock_db(plan, count=3)
        tenant = make_tenant()
        with pytest.raises(UserLimitReachedError):
            self.svc.check_user_limit(db, tenant)

    def test_package_limit_reached(self):
        plan = make_plan(max_packages=5)
        db = self._mock_db(plan, count=5)
        tenant = make_tenant()
        with pytest.raises(PackageLimitReachedError):
            self.svc.check_package_limit(db, tenant)

    def test_override_takes_precedence_over_plan(self):
        """Override com limite menor que plano deve valer."""
        plan = make_plan(max_services=100)
        override = MagicMock()
        override.max_services = 2
        override.max_professionals = None
        override.max_users = None
        override.max_appointments_per_month = None
        override.max_units = None
        override.max_packages = None
        db = self._mock_db(plan, override=override, count=2)
        tenant = make_tenant()
        with pytest.raises(ServiceLimitReachedError):
            self.svc.check_service_limit(db, tenant)


class TestFeatureFlagService:
    def setup_method(self):
        self.svc = FeatureFlagService()

    def _make_db(self, flag=None, plan=None, sub=None):
        db = MagicMock()

        flag_q = MagicMock()
        flag_q.filter.return_value.first.return_value = flag

        sub_q = MagicMock()
        sub_q.filter.return_value.order_by.return_value.first.return_value = sub

        plan_q = MagicMock()
        plan_q.filter.return_value.first.return_value = plan

        def side_effect(model):
            from app.models.tenant import TenantFeatureFlag, TenantSubscription
            from app.models.plan import Plan
            if model is TenantFeatureFlag:
                return flag_q
            elif model is TenantSubscription:
                return sub_q
            elif model is Plan:
                return plan_q
            return MagicMock()

        db.query.side_effect = side_effect
        return db

    def test_flag_enabled_by_override(self):
        flag = MagicMock()
        flag.enabled = True
        db = self._make_db(flag=flag)
        tenant = make_tenant()
        assert self.svc.is_enabled(db, tenant, "webhooks") is True

    def test_flag_disabled_by_override(self):
        flag = MagicMock()
        flag.enabled = False
        db = self._make_db(flag=flag)
        tenant = make_tenant()
        assert self.svc.is_enabled(db, tenant, "webhooks") is False

    def test_flag_from_plan(self):
        plan = MagicMock()
        plan.allow_webhooks = True
        sub = MagicMock()
        sub.plan_id = uuid4()
        db = self._make_db(flag=None, plan=plan, sub=sub)
        tenant = make_tenant()
        assert self.svc.is_enabled(db, tenant, "webhooks") is True

    def test_require_feature_raises_when_disabled(self):
        flag = MagicMock()
        flag.enabled = False
        db = self._make_db(flag=flag)
        tenant = make_tenant()
        with pytest.raises(FeatureDisabledError):
            self.svc.require_feature(db, tenant, "webhooks")

    def test_require_feature_passes_when_enabled(self):
        flag = MagicMock()
        flag.enabled = True
        db = self._make_db(flag=flag)
        tenant = make_tenant()
        # Should not raise
        self.svc.require_feature(db, tenant, "webhooks")
