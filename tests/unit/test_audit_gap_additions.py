"""Smoke tests for audit-gap additions. These tests validate imports and route registration."""
from app.main import app
from app.models.tenant import TenantPaymentSettings, TenantBookingPolicy
from app.models.package import PackageService
from app.models.appointment import Appointment, AppointmentService
from app.models.unit import Unit
from app.models.future import AppointmentReview, Coupon, AppointmentHold


def test_audit_gap_models_exist():
    assert TenantPaymentSettings.__tablename__ == "tenant_payment_settings"
    assert PackageService.__tablename__ == "package_services"
    assert AppointmentReview.__tablename__ == "appointment_reviews"
    assert Coupon.__tablename__ == "coupons"
    assert AppointmentHold.__tablename__ == "appointment_holds"
    assert hasattr(TenantBookingPolicy, "no_show_limit_before_deposit_required")
    assert hasattr(Appointment, "uses_package")
    assert hasattr(AppointmentService, "package_session_id")
    assert hasattr(Unit, "whatsapp")


def test_audit_gap_routes_registered():
    routes = {(route.path, method) for route in app.routes if hasattr(route, "methods") for method in route.methods}
    expected = {
        ("/api/v1/settings/payment", "GET"),
        ("/api/v1/settings/payment", "PUT"),
        ("/api/v1/packages/{package_id}/services", "GET"),
        ("/api/v1/packages/{package_id}/services", "POST"),
        ("/api/v1/packages/{package_id}/services/{service_id}", "DELETE"),
        ("/api/v1/customer/me", "GET"),
        ("/api/v1/customer/me", "PUT"),
        ("/api/v1/customer/tenants/{slug}/profile", "GET"),
        ("/api/v1/customer/tenants/{slug}/appointments", "GET"),
        ("/api/v1/customer/tenants/{slug}/packages", "GET"),
        ("/api/v1/customer/tenants/{slug}/procedure-history", "GET"),
        ("/api/v1/reviews", "GET"),
        ("/api/v1/coupons", "GET"),
        ("/api/v1/appointment-holds", "POST"),
    }
    missing = expected - routes
    assert not missing


def test_final_prompt_closure_models_and_routes():
    from app.models.customer import CustomerTagLink, CustomerNote
    from app.models.professional import Professional
    from app.models.resource import Resource
    from app.models.schedule import BusinessHour
    from app.models.tenant import ThemePreset

    assert CustomerTagLink.__table__.c.tenant_id.nullable is False
    assert CustomerNote.__table__.c.note.nullable is False
    assert CustomerNote.__table__.c.visibility.nullable is False
    assert hasattr(Professional, "unit_id")
    assert hasattr(Resource, "unit_id")
    assert hasattr(BusinessHour, "unit_id")
    assert ThemePreset.__tablename__ == "theme_presets"

    routes = {(route.path, method) for route in app.routes if hasattr(route, "methods") for method in route.methods}
    expected = {
        ("/api/v1/master/plans/{plan_id}", "GET"),
        ("/api/v1/master/tenants/{tenant_id}/settings", "GET"),
        ("/api/v1/master/tenants/{tenant_id}/theme", "GET"),
    }
    assert expected.issubset(routes)
