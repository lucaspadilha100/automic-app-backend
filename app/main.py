from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.error_handlers import (
    app_error_handler,
    validation_error_handler,
    http_exception_handler,
    generic_exception_handler,
)
from app.core.logging_config import configure_logging
from app.core.middleware import (
    RequestContextMiddleware, install_log_filter,
)
from app.core.sentry_setup import init_sentry

# Initialize logging as the very first thing so all subsequent imports log
# through the configured handler/formatter.
configure_logging()
install_log_filter()
# Sentry — no-op if SENTRY_DSN unset or sdk not installed.
init_sentry()

# ---- Routes ----
from app.api.routes.auth import router as auth_router
from app.api.routes.customer_auth import router as customer_auth_router
from app.api.routes.master_tenants import router as master_router
from app.api.routes.services import router as services_router
from app.api.routes.professionals import router as professionals_router
from app.api.routes.appointments import router as appointments_router
from app.api.routes.customers import router as customers_router
from app.api.routes.availability import router as availability_router
from app.api.routes.public import router as public_router
from app.api.routes.packages import router as packages_router
from app.api.routes.users import router as users_router
from app.api.routes.settings import router as settings_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.units_waitlist import units_router, waitlist_router
from app.api.routes.payments import router as payments_router
from app.api.routes.resources import router as resources_router
from app.api.routes.audit import router as audit_router
from app.api.routes.media import router as media_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.schedule import router as schedule_router
from app.api.routes.future import router as future_router
from app.api.routes.customer_portal import router as customer_portal_router
from app.api.routes.admin_terms import router as admin_terms_router
from app.api.routes.customer_terms import router as customer_terms_router
from app.api.routes.admin_procedure_photos import router as admin_procedure_photos_router, history_router as admin_procedure_history_router
from app.api.routes.customer_procedure_photos import router as customer_procedure_photos_router
from app.api.routes.admin_commissions import router as admin_commissions_router
from app.api.routes.admin_custom_forms import router as admin_custom_forms_router
from app.api.routes.admin_customer_lifecycle import router as admin_lifecycle_router, customers_router as admin_lifecycle_customers_router
from app.api.routes.admin_automations import router as admin_automations_router
from app.api.routes.admin_whatsapp_settings import router as admin_whatsapp_router
from app.api.routes.customer_custom_forms import router as customer_custom_forms_router
from app.api.routes.master_platform import (
    router as master_platform_router,
    public_router as public_platform_router,
)
from app.api.routes.support_tenant import router as support_tenant_router
from app.api.routes.master_support import router as master_support_router
from app.api.routes.master_notifications import router as master_notifications_router
from app.api.routes.public_signup import router as public_signup_router
from app.api.routes.master_ops import router as master_ops_router
from app.api.routes.master_invoices import (
    router as master_invoices_router,
    jobs_router as master_invoice_jobs_router,
)
from app.api.routes.master_tasks import router as master_tasks_router
from app.api.routes.master_billing_manual import router as master_billing_manual_router
from app.api.routes.schedule_exceptions import (
    router as schedule_exceptions_router,
    bulk_router as appointments_bulk_router,
)
from app.api.routes.products import (
    router as products_router,
    public_router as products_public_router,
    categories_router as product_categories_router,
    orders_router as product_orders_router,
)
from app.api.routes.supplies import router as supplies_router, usage_router as supply_usage_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description=(
        "AUTOMIC Booking Backend — SaaS white label multi-tenant de agendamento. "
        "Documentação completa para integração com o painel administrativo e a página pública."
    ),
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# ---- CORS ----
_cors_origins = settings.BACKEND_CORS_ORIGINS or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=bool(settings.BACKEND_CORS_ORIGINS),
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Request context (request_id + structured access log) ----
app.add_middleware(RequestContextMiddleware)

# ---- Exception Handlers ----
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# ---- API Prefix ----
API_V1 = "/api/v1"

# Public (no auth required)
app.include_router(public_router, prefix=API_V1)
app.include_router(availability_router, prefix=API_V1)

# Auth
app.include_router(auth_router, prefix=API_V1)
app.include_router(customer_auth_router, prefix=API_V1)

# Master (super_admin)
app.include_router(master_router, prefix=API_V1)

# Tenant panel (authenticated)
app.include_router(services_router, prefix=API_V1)
app.include_router(professionals_router, prefix=API_V1)
app.include_router(appointments_router, prefix=API_V1)
app.include_router(customers_router, prefix=API_V1)
app.include_router(packages_router, prefix=API_V1)
app.include_router(users_router, prefix=API_V1)
app.include_router(settings_router, prefix=API_V1)
app.include_router(dashboard_router, prefix=API_V1)
app.include_router(units_router, prefix=API_V1)
app.include_router(waitlist_router, prefix=API_V1)
app.include_router(payments_router, prefix=API_V1)
app.include_router(resources_router, prefix=API_V1)
app.include_router(audit_router, prefix=API_V1)
app.include_router(media_router, prefix=API_V1)
app.include_router(notifications_router, prefix=API_V1)
app.include_router(schedule_router, prefix=API_V1)
app.include_router(future_router, prefix=API_V1)
app.include_router(customer_portal_router, prefix=API_V1)
app.include_router(admin_terms_router, prefix=API_V1)
app.include_router(customer_terms_router, prefix=API_V1)
app.include_router(admin_procedure_history_router, prefix=API_V1)
app.include_router(admin_procedure_photos_router, prefix=API_V1)
app.include_router(customer_procedure_photos_router, prefix=API_V1)
app.include_router(admin_commissions_router, prefix=API_V1)
app.include_router(admin_custom_forms_router, prefix=API_V1)
app.include_router(admin_lifecycle_router, prefix=API_V1)
app.include_router(admin_lifecycle_customers_router, prefix=API_V1)
app.include_router(admin_automations_router, prefix=API_V1)
app.include_router(admin_whatsapp_router, prefix=API_V1)
app.include_router(customer_custom_forms_router, prefix=API_V1)
app.include_router(master_platform_router, prefix=API_V1)
app.include_router(public_platform_router, prefix=API_V1)
app.include_router(support_tenant_router, prefix=API_V1)
app.include_router(master_support_router, prefix=API_V1)
app.include_router(master_notifications_router, prefix=API_V1)
app.include_router(public_signup_router, prefix=API_V1)
app.include_router(master_ops_router, prefix=API_V1)
app.include_router(master_invoices_router, prefix=API_V1)
app.include_router(master_invoice_jobs_router, prefix=API_V1)
app.include_router(master_tasks_router, prefix=API_V1)
app.include_router(master_billing_manual_router, prefix=API_V1)
app.include_router(schedule_exceptions_router, prefix=API_V1)
app.include_router(appointments_bulk_router, prefix=API_V1)
app.include_router(product_categories_router, prefix=API_V1)
app.include_router(products_router, prefix=API_V1)
app.include_router(product_orders_router, prefix=API_V1)
app.include_router(products_public_router, prefix=API_V1)
app.include_router(supplies_router, prefix=API_V1)
app.include_router(supply_usage_router, prefix=API_V1)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health/live", tags=["Health"])
def health_live():
    """
    Liveness probe — returns 200 as long as the process is running.
    Used by Docker/k8s to decide if the container needs to be restarted.
    Never checks external dependencies — those go on /health/ready.
    """
    return {"status": "alive"}


@app.get("/health/ready", tags=["Health"])
def health_ready():
    """
    Readiness probe — returns 200 only when the app is ready to serve traffic.

    Checks:
      - Postgres reachable
      - Redis reachable (only if REDIS_URL is set; otherwise treated as N/A)

    Returns 503 with details if any dependency is unhealthy.
    """
    import os
    from db.session import engine
    from sqlalchemy import text
    from fastapi.responses import JSONResponse

    deps = {}
    overall_ok = True

    # Postgres check
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        deps["database"] = {"status": "up"}
    except Exception as e:
        deps["database"] = {"status": "down", "detail": str(e)[:200]}
        overall_ok = False

    # Redis check (optional)
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        try:
            import redis  # type: ignore
            r = redis.Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
            r.ping()
            deps["redis"] = {"status": "up"}
        except Exception as e:
            deps["redis"] = {"status": "down", "detail": str(e)[:200]}
            overall_ok = False
    else:
        deps["redis"] = {"status": "not_configured"}

    body = {"status": "ready" if overall_ok else "not_ready", "dependencies": deps}
    if overall_ok:
        return body
    return JSONResponse(status_code=503, content=body)


@app.get("/health/db", tags=["Health"])
def health_db():
    """Verifica conexão com o banco de dados."""
    from db.session import engine
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        from fastapi import Response
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "disconnected", "detail": str(e)},
        )


@app.get("/health/full", tags=["Health"])
def health_full():
    """Verificação completa: API + banco + modelos."""
    import platform
    from db.session import engine
    from sqlalchemy import text, inspect
    result = {
        "status": "ok",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "python": platform.python_version(),
        "database": "unknown",
        "tables": [],
    }
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        insp = inspect(engine)
        result["database"] = "connected"
        result["tables"] = sorted(insp.get_table_names())
    except Exception as e:
        result["status"] = "degraded"
        result["database"] = f"error: {str(e)}"
    return result


@app.get("/", tags=["Root"])
def root():
    return {"message": f"{settings.PROJECT_NAME} está no ar! 🚀"}
