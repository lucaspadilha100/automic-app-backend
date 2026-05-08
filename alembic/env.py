from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os, sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import settings
from db.base import Base

# Import all models so Alembic can detect them
from app.models.plan import Plan
from app.models.tenant import (
    Tenant, TenantSubscription, TenantLimitOverride,
    TenantFeatureFlag, TenantSettings, TenantTheme, ThemePreset, TenantBookingPolicy, TenantPaymentSettings
)
from app.models.user import User, PasswordResetToken, UserInvite
from app.models.customer import CustomerAccount, TenantCustomer, CustomerTag, CustomerTagLink, CustomerNote
from app.models.service import ServiceCategory, Service, ProfessionalService
from app.models.professional import Professional, ProfessionalAvailability
from app.models.schedule import BusinessHour, BlockedTime
from app.models.appointment import Appointment, AppointmentService, AppointmentStatusHistory, IdempotencyKey
from app.models.payment import Payment
from app.models.package import Package, PackageService, CustomerPackage, PackageSession
from app.models.procedure import ProcedureHistory
from app.models.event import CustomerEvent
from app.models.audit import AuditLog
from app.models.notification import NotificationTemplate, NotificationLog
from app.models.webhook import WebhookEndpoint, WebhookDelivery
from app.models.media import MediaFile
from app.models.resource import Resource, ServiceResource, AppointmentResource
from app.models.waitlist import WaitlistEntry
from app.models.unit import Unit
from app.models.future import AppointmentReview, Coupon, AppointmentHold
from app.models.term import TenantTerm, CustomerTermAcceptance
from app.models.procedure_photo import ProcedurePhoto
from app.models.commission import ProfessionalCommissionSetting, CommissionRecord
from app.models.custom_form import CustomForm, CustomFormField, CustomFormResponse as CustomFormResponseModel
from app.models.customer_lifecycle import TenantLifecycleSetting
from app.models.automation import AutomationRule
from app.models.whatsapp import TenantWhatsAppSettings
from app.models.platform_settings import PlatformSettings
from app.models.support_ticket import SupportTicket, SupportTicketMessage
from app.models.owner_notification import OwnerNotification
from app.models.platform_document import PlatformDocument
from app.models.tenant_invoice import TenantInvoice
from app.models.task_run import TaskRun
from app.models.schedule_exception import ScheduleException

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # Some revision identifiers in this project exceed the default
        # alembic_version column width of varchar(32). Pre-create / widen
        # the table so upgrades and stamps don't truncate.
        from sqlalchemy import text as _sql_text
        try:
            connection.execute(_sql_text(
                "CREATE TABLE IF NOT EXISTS alembic_version "
                "(version_num VARCHAR(64) NOT NULL, "
                "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
            ))
            connection.execute(_sql_text(
                "ALTER TABLE alembic_version "
                "ALTER COLUMN version_num TYPE VARCHAR(64)"
            ))
            connection.commit()
        except Exception:
            # If the connection's dialect doesn't support these statements
            # (e.g. SQLite during local CI), let Alembic fall back to default behavior.
            connection.rollback()

        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
