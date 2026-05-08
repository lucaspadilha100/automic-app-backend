"""
Seed script — execute com:
  python scripts/seed.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.session import SessionLocal
from app.core.config import settings
from app.core.security import hash_password

# Importar TODOS os models para resolver relacionamentos SQLAlchemy
from app.models.plan import Plan
from app.models.tenant import Tenant, TenantSettings, TenantTheme, ThemePreset, TenantBookingPolicy, TenantPaymentSettings, TenantSubscription
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
# Expansion-1 models — required so SQLAlchemy can resolve back-relationships
from app.models.term import TenantTerm, CustomerTermAcceptance
from app.models.procedure_photo import ProcedurePhoto
from app.models.commission import ProfessionalCommissionSetting, CommissionRecord
from app.models.custom_form import CustomForm, CustomFormField, CustomFormResponse
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
from datetime import datetime, timezone

db = SessionLocal()


def seed_plans():
    if db.query(Plan).count() > 0:
        print("⏭  Planos já existem, pulando...")
        return

    plans = [
        # Starter — entry plan, low ticket. Most premium features off.
        Plan(
            name="Starter",
            description="Plano de entrada para profissionais e pequenos negócios.",
            price_monthly=97,
            max_services=20,
            max_professionals=2,
            max_users=3,
            max_appointments_per_month=300,
            max_units=1,
            max_packages=3,
            allow_packages=True,
            allow_custom_terms=False,
            allow_before_after_photos=False,
            allow_commissions=False,
            allow_custom_forms=False,
            allow_customer_lifecycle=False,
            allow_automation_rules=False,
            allow_whatsapp_integration=False,
            allow_online_payment=False,
            allow_advanced_reports=False,
            allow_crm_integration=False,
            allow_multi_unit=False,
            allow_waitlist=False,
            allow_physical_resources=False,
            allow_webhooks=False,
        ),
        # Pro — most professional features ON, but no automation, online payment, multi-unit.
        Plan(
            name="Pro",
            description="Plano para pequenas equipes com pacotes, lista de espera, comissões, anamnese e WhatsApp.",
            price_monthly=197,
            max_services=100,
            max_professionals=8,
            max_users=10,
            max_appointments_per_month=2000,
            max_units=1,
            max_packages=20,
            allow_packages=True,
            allow_custom_terms=True,
            allow_before_after_photos=True,
            allow_commissions=True,
            allow_custom_forms=True,
            allow_customer_lifecycle=True,
            allow_automation_rules=True,
            allow_whatsapp_integration=True,
            allow_online_payment=False,
            allow_advanced_reports=True,
            allow_crm_integration=True,
            allow_multi_unit=False,
            allow_waitlist=True,
            allow_physical_resources=True,
            allow_webhooks=True,
        ),
        # Premium — full feature set including multi-unit, automation rules and webhooks.
        Plan(
            name="Premium",
            description="Plano completo para clínicas, salões maiores, multiunidade e automações.",
            price_monthly=347,
            max_services=1000,
            max_professionals=100,
            max_users=100,
            max_appointments_per_month=20000,
            max_units=5,
            max_packages=1000,
            allow_packages=True,
            allow_custom_terms=True,
            allow_before_after_photos=True,
            allow_commissions=True,
            allow_custom_forms=True,
            allow_customer_lifecycle=True,
            allow_automation_rules=True,
            allow_whatsapp_integration=True,
            allow_online_payment=True,
            allow_advanced_reports=True,
            allow_crm_integration=True,
            allow_multi_unit=True,
            allow_waitlist=True,
            allow_physical_resources=True,
            allow_webhooks=True,
        ),
    ]

    for p in plans:
        db.add(p)
    db.commit()
    print(f"✅ {len(plans)} planos criados.")


def seed_theme_presets():
    presets = [
        ("estetica_premium", "Estética Premium", "#7C3AED", "#C4B5FD", "#FFFFFF", "#7C3AED", "#111827", "Inter", "premium"),
        ("barbearia_dark", "Barbearia Dark", "#111827", "#D4AF37", "#0B0F19", "#D4AF37", "#F9FAFB", "Inter", "dark"),
        ("salao_clean", "Salão Clean", "#EC4899", "#F9A8D4", "#FFFFFF", "#EC4899", "#111827", "Inter", "clean"),
        ("clinica_minimalista", "Clínica Minimalista", "#0F766E", "#99F6E4", "#F8FAFC", "#0F766E", "#0F172A", "Inter", "minimal"),
        ("spa_natural", "Spa Natural", "#65A30D", "#BEF264", "#FAFAF5", "#65A30D", "#1F2937", "Inter", "natural"),
        ("lash_brow_feminino", "Lash & Brow Feminino", "#BE185D", "#FBCFE8", "#FFF7FB", "#BE185D", "#3B0A1E", "Inter", "feminine"),
    ]
    created = 0
    for key, name, primary, secondary, bg, button, text, font, style in presets:
        if db.query(ThemePreset).filter(ThemePreset.key == key).first():
            continue
        db.add(ThemePreset(
            key=key, name=name, primary_color=primary, secondary_color=secondary,
            background_color=bg, button_color=button, text_color=text,
            font_family=font, visual_style=style, is_active=True,
        ))
        created += 1
    db.commit()
    print(f"✅ {created} presets de tema criados.")


def seed_super_admin():
    exists = db.query(User).filter(User.email == settings.FIRST_SUPER_ADMIN_EMAIL).first()
    if exists:
        print("⏭  Super admin já existe, pulando...")
        return

    admin = User(
        email=settings.FIRST_SUPER_ADMIN_EMAIL,
        name=settings.FIRST_SUPER_ADMIN_NAME,
        role="super_admin",
        password_hash=hash_password(settings.FIRST_SUPER_ADMIN_PASSWORD),
        is_active=True,
    )
    db.add(admin)
    db.commit()
    print(f"✅ Super admin criado: {settings.FIRST_SUPER_ADMIN_EMAIL}")


def seed_demo_tenant():
    if db.query(Tenant).filter(Tenant.slug == "demo").first():
        print("⏭  Tenant demo já existe, pulando...")
        return

    tenant = Tenant(
        name="Studio Demo",
        slug="demo",
        status="active",
        timezone="America/Sao_Paulo",
        public_name="Studio Demo",
        short_description="Bem-vindo ao Studio Demo da plataforma AUTOMIC!",
        category="Estética",
        phone="(84) 99999-0000",
        whatsapp="5584999990000",
        email="demo@automiq.com.br",
    )
    db.add(tenant)
    db.flush()

    db.add(TenantSettings(tenant_id=tenant.id))
    db.add(TenantTheme(tenant_id=tenant.id, primary_color="#7C3AED", secondary_color="#A78BFA"))
    db.add(TenantBookingPolicy(tenant_id=tenant.id))
    db.add(TenantPaymentSettings(tenant_id=tenant.id, manual_payment_instructions="Faça o Pix e envie o comprovante pelo WhatsApp.", pix_key="demo@automiq.com.br"))
    db.add(Unit(
        tenant_id=tenant.id,
        name="Unidade Principal",
        address=tenant.address,
        phone=tenant.phone,
        whatsapp=tenant.whatsapp,
        email=tenant.email,
        timezone=tenant.timezone,
        is_main=True,
        is_active=True,
    ))

    plan = db.query(Plan).filter(Plan.name == "Pro").first()
    if plan:
        db.add(TenantSubscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status="active",
            starts_at=datetime.now(timezone.utc),
        ))

    owner = User(
        tenant_id=tenant.id,
        email="owner@demo.com",
        name="Proprietário Demo",
        role="tenant_owner",
        password_hash=hash_password("Demo@2024!"),
        is_active=True,
    )
    db.add(owner)

    # ── Profissional demo ──────────────────────────────────────────────────
    professional = Professional(
        tenant_id=tenant.id,
        name="Dra. Ana Silva",
        email="ana@studio-demo.com",
        phone="(84) 99999-1111",
        bio="Especialista em estética facial e corporal. 10 anos de experiência.",
        is_active=True,
    )
    db.add(professional)
    db.flush()

    # ── Horários de trabalho do profissional ──────────────────────────────
    for weekday, start, end in [(1,'09:00','18:00'),(2,'09:00','18:00'),(3,'09:00','18:00'),(4,'09:00','18:00'),(5,'09:00','18:00'),(6,'09:00','13:00')]:
        db.add(ProfessionalAvailability(
            tenant_id=tenant.id,
            professional_id=professional.id,
            weekday=weekday,
            start_time=start,
            end_time=end,
            is_available=True,
        ))

    # ── Horário de funcionamento da clínica ───────────────────────────────
    for weekday, open_t, close_t, closed in [(0,None,None,True),(1,'09:00','18:00',False),(2,'09:00','18:00',False),(3,'09:00','18:00',False),(4,'09:00','18:00',False),(5,'09:00','18:00',False),(6,'09:00','13:00',False)]:
        db.add(BusinessHour(
            tenant_id=tenant.id,
            weekday=weekday,
            open_time=open_t,
            close_time=close_t,
            is_closed=closed,
        ))

    # ── Categoria e serviços ──────────────────────────────────────────────
    cat = ServiceCategory(tenant_id=tenant.id, name="Estética Facial", sort_order=0, is_active=True)
    db.add(cat)
    db.flush()

    servicos = [
        {"name": "Limpeza de Pele", "duration_minutes": 60, "price": 150.00, "description": "Limpeza profunda com extração"},
        {"name": "Hidratação Facial", "duration_minutes": 45, "price": 120.00, "description": "Hidratação com ácido hialurônico"},
        {"name": "Design de Sobrancelha", "duration_minutes": 30, "price": 60.00, "description": "Design e coloração de sobrancelha"},
    ]

    for sv_data in servicos:
        sv = Service(
            tenant_id=tenant.id,
            category_id=cat.id,
            name=sv_data["name"],
            description=sv_data["description"],
            duration_minutes=sv_data["duration_minutes"],
            buffer_before_minutes=0,
            buffer_after_minutes=0,
            price=sv_data["price"],
            requires_deposit=False,
            deposit_type="none",
            deposit_value=0,
            is_active=True,
        )
        db.add(sv)
        db.flush()
        db.add(ProfessionalService(
            tenant_id=tenant.id,
            professional_id=professional.id,
            service_id=sv.id,
        ))

    db.commit()
    print(f"✅ Tenant demo criado. Owner: owner@demo.com / Demo@2024!")


if __name__ == "__main__":
    print("🌱 Iniciando seed...")
    seed_plans()
    seed_theme_presets()
    seed_super_admin()
    seed_demo_tenant()
    db.close()
    print("🎉 Seed concluído!")
