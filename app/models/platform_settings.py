"""
Platform settings — configuration of the AUTOMIC platform itself.

This is a *singleton* table (always exactly one row, identified by
`is_singleton = True` enforced by a unique constraint). It stores the
identity, branding and contact info of the SaaS owner — everything
that should be visible in the master console, in cobrança emails and
in any tenant-facing footer/legal page.

This is **separate** from `TenantTheme` and `TenantSettings`, which
configure the *tenant's* white-label identity. Don't confuse them.
"""
from sqlalchemy import Column, String, Boolean, Text, UniqueConstraint
from app.models.base_model import UUIDPrimaryKey, TimestampMixin
from db.base import Base


class PlatformSettings(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "platform_settings"
    __table_args__ = (
        UniqueConstraint("is_singleton", name="uq_platform_settings_singleton"),
    )

    # Singleton enforcement: always set to True; unique constraint ensures one row.
    is_singleton = Column(Boolean, nullable=False, default=True)

    # ── Identity ────────────────────────────────────────────────────────────
    platform_name = Column(String(100), nullable=False, default="AUTOMIC")
    platform_tagline = Column(String(255), nullable=True,
                              default="Sistemas inteligentes. Automação real.")
    platform_legal_name = Column(String(255), nullable=True)  # Razão social, ex: AUTOMIC.TECH LTDA
    platform_cnpj = Column(String(20), nullable=True)

    # ── Branding ────────────────────────────────────────────────────────────
    logo_url = Column(String(500), nullable=True)         # URL pública da logo (PNG/SVG)
    logo_dark_url = Column(String(500), nullable=True)    # Versão pra dark mode (master console)
    favicon_url = Column(String(500), nullable=True)
    primary_color = Column(String(20), nullable=False, default="#22D3EE")    # Cyan AUTOMIC
    secondary_color = Column(String(20), nullable=False, default="#0F172A")  # Slate 900
    accent_color = Column(String(20), nullable=True, default="#06B6D4")

    # ── Contato e suporte ───────────────────────────────────────────────────
    support_email = Column(String(255), nullable=True)
    support_phone = Column(String(30), nullable=True)
    support_url = Column(String(500), nullable=True)       # Link pra portal de suporte/whatsapp
    sales_email = Column(String(255), nullable=True)
    sales_phone = Column(String(30), nullable=True)

    # ── Domínio e marketing ─────────────────────────────────────────────────
    primary_domain = Column(String(255), nullable=True)    # automic.tech
    marketing_url = Column(String(500), nullable=True)     # https://automic.tech
    instagram_url = Column(String(500), nullable=True)
    linkedin_url = Column(String(500), nullable=True)

    # ── Legal ───────────────────────────────────────────────────────────────
    terms_of_service_url = Column(String(500), nullable=True)
    privacy_policy_url = Column(String(500), nullable=True)

    # ── Notificações ao dono ────────────────────────────────────────────────
    # Emails (separados por vírgula) que recebem alertas operacionais:
    # novo tenant, cancelamento, falha de pagamento, etc.
    owner_notification_emails = Column(Text, nullable=True)

    # ── Metadata extra (free-form) ──────────────────────────────────────────
    notes = Column(Text, nullable=True)
