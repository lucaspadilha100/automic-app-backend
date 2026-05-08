import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.notification import NotificationTemplate, NotificationLog
from app.models.appointment import Appointment
from app.models.customer import CustomerAccount

logger = logging.getLogger(__name__)

# Template variable mapping
APPOINTMENT_VARS = {
    "{{customer_name}}",
    "{{professional_name}}",
    "{{service_name}}",
    "{{appointment_date}}",
    "{{appointment_time}}",
    "{{tenant_name}}",
    "{{tenant_phone}}",
    "{{cancellation_policy}}",
}


class NotificationService:

    def _render_template(self, body: str, context: dict) -> str:
        for key, value in context.items():
            body = body.replace(f"{{{{{key}}}}}", str(value or ""))
        return body

    def _build_context(self, appointment: Appointment) -> dict:
        import pytz
        prof = appointment.professional
        services = appointment.appointment_services
        service_names = ", ".join(s.service_name_snapshot for s in services)

        tz = pytz.timezone(appointment.tenant.timezone or "America/Sao_Paulo")
        start_local = appointment.start_datetime.astimezone(tz)

        return {
            "customer_name": appointment.customer_account.name if appointment.customer_account else "",
            "professional_name": prof.name if prof else "",
            "service_name": service_names,
            "appointment_date": start_local.strftime("%d/%m/%Y"),
            "appointment_time": start_local.strftime("%H:%M"),
            "tenant_name": appointment.tenant.public_name or appointment.tenant.name,
            "tenant_phone": appointment.tenant.phone or "",
        }

    def send_appointment_notification(
        self,
        db: Session,
        event_type: str,
        appointment: Appointment,
    ) -> None:
        """
        Busca templates ativos para o evento e dispara por cada canal habilitado.
        Em produção: substituir _send_whatsapp/_send_email por integrações reais.
        """
        templates = (
            db.query(NotificationTemplate)
            .filter(
                NotificationTemplate.tenant_id == appointment.tenant_id,
                NotificationTemplate.event_type == event_type,
                NotificationTemplate.is_active == True,
            )
            .all()
        )

        if not templates:
            return

        context = self._build_context(appointment)

        for tmpl in templates:
            rendered_body = self._render_template(tmpl.body, context)
            rendered_subject = self._render_template(tmpl.subject or "", context)

            log = NotificationLog(
                tenant_id=appointment.tenant_id,
                customer_account_id=appointment.customer_account_id,
                appointment_id=appointment.id,
                channel=tmpl.channel,
                event_type=event_type,
                status="pending",
            )
            db.add(log)
            db.flush()

            try:
                if tmpl.channel == "whatsapp":
                    self._send_whatsapp(appointment, rendered_body)
                elif tmpl.channel == "email":
                    self._send_email(appointment, rendered_subject, rendered_body)
                elif tmpl.channel == "sms":
                    self._send_sms(appointment, rendered_body)
                log.status = "sent"
                log.sent_at = datetime.now(timezone.utc)
            except Exception as exc:
                logger.warning(f"Notification failed [{tmpl.channel}] {event_type}: {exc}")
                log.status = "failed"
                log.error_message = str(exc)[:500]
            db.add(log)
        # Commit all logs at once at the end
        db.commit()

    def _send_whatsapp(self, appointment: Appointment, body: str) -> None:
        phone = appointment.customer_account.phone if appointment.customer_account else None
        if not phone:
            raise ValueError("Cliente sem telefone cadastrado.")
        from app.services.notification_provider import get_notification_provider
        result = get_notification_provider().send_whatsapp(to=phone, body=body)
        if not result.success:
            raise RuntimeError(result.error_message or "WhatsApp send failed")

    def _send_email(self, appointment: Appointment, subject: str, body: str) -> None:
        email = appointment.customer_account.email if appointment.customer_account else None
        if not email:
            raise ValueError("Cliente sem e-mail cadastrado.")
        from app.services.notification_provider import get_notification_provider
        result = get_notification_provider().send_email(to=email, subject=subject, body=body)
        if not result.success:
            raise RuntimeError(result.error_message or "Email send failed")

    def _send_sms(self, appointment: Appointment, body: str) -> None:
        phone = appointment.customer_account.phone if appointment.customer_account else None
        if not phone:
            raise ValueError("Cliente sem telefone cadastrado.")
        from app.services.notification_provider import get_notification_provider
        result = get_notification_provider().send_sms(to=phone, body=body)
        if not result.success:
            raise RuntimeError(result.error_message or "SMS send failed")

    def get_logs(
        self, db: Session, tenant_id: UUID,
        event_type: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0, limit: int = 50,
    ) -> list:
        q = db.query(NotificationLog).filter(NotificationLog.tenant_id == tenant_id)
        if event_type:
            q = q.filter(NotificationLog.event_type == event_type)
        if status:
            q = q.filter(NotificationLog.status == status)
        return q.order_by(NotificationLog.created_at.desc()).offset(skip).limit(limit).all()

    # ── Generic send (Expansion 3) ───────────────────────────────────────────
    # Used by jobs that don't have an Appointment context (signup welcome,
    # invoice reminders, generic platform notifications). Uses DEFAULT_TEMPLATES
    # if the tenant doesn't have a custom NotificationTemplate row.

    def send_generic(
        self,
        db: Session,
        tenant_id: UUID,
        channel: str,
        event_type: str,
        to: str,
        context: Optional[dict] = None,
        appointment_id: Optional[UUID] = None,
        customer_account_id: Optional[UUID] = None,
        skip_if_already_sent: bool = False,
    ) -> NotificationLog:
        from app.services.notification_provider import get_notification_provider, SendResult
        context = context or {}

        if skip_if_already_sent:
            existing_q = db.query(NotificationLog).filter(
                NotificationLog.tenant_id == tenant_id,
                NotificationLog.event_type == event_type,
                NotificationLog.channel == channel,
                NotificationLog.status == "sent",
            )
            if appointment_id:
                existing_q = existing_q.filter(NotificationLog.appointment_id == appointment_id)
            if customer_account_id:
                existing_q = existing_q.filter(
                    NotificationLog.customer_account_id == customer_account_id,
                )
            existing = existing_q.first()
            if existing:
                return existing

        # Resolve template (custom or built-in default)
        tpl = self._resolve_template(db, tenant_id, event_type, channel)
        subject = self._render_template(tpl.get("subject", ""), context)
        body = self._render_template(tpl["body"], context)

        log = NotificationLog(
            tenant_id=tenant_id,
            customer_account_id=customer_account_id,
            appointment_id=appointment_id,
            channel=channel,
            event_type=event_type,
            status="pending",
        )
        db.add(log)
        db.flush()

        provider = get_notification_provider()
        try:
            if channel == "email":
                result = provider.send_email(to=to, subject=subject, body=body)
            elif channel == "sms":
                result = provider.send_sms(to=to, body=body)
            elif channel == "whatsapp":
                result = provider.send_whatsapp(to=to, body=body)
            else:
                result = SendResult(
                    success=False, provider="unknown",
                    error_message=f"Channel '{channel}' não suportado",
                )
        except NotImplementedError as e:
            result = SendResult(success=False, provider="unknown", error_message=str(e))
        except Exception as e:
            logger.exception("send_generic raised")
            result = SendResult(success=False, provider="unknown", error_message=str(e)[:500])

        log.provider = result.provider
        if result.success:
            log.status = "sent"
            log.sent_at = datetime.now(timezone.utc)
        else:
            log.status = "failed"
            log.error_message = result.error_message
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    def _resolve_template(
        self, db: Session, tenant_id: UUID, event_type: str, channel: str,
    ) -> dict:
        custom = (
            db.query(NotificationTemplate)
            .filter(
                NotificationTemplate.tenant_id == tenant_id,
                NotificationTemplate.event_type == event_type,
                NotificationTemplate.channel == channel,
                NotificationTemplate.is_active == True,
            )
            .first()
        )
        if custom:
            return {"subject": custom.subject or "", "body": custom.body}
        default = DEFAULT_TEMPLATES.get(event_type, {}).get(channel)
        if default:
            return {"subject": default.get("subject", ""), "body": default["body"]}
        return {"subject": event_type, "body": f"[{event_type}]"}


# ── Built-in default templates for Expansion 3 events ───────────────────────
# Variables use {{var}} (double brace) to match the existing _render_template.
DEFAULT_TEMPLATES = {
    "appointment_reminder_24h": {
        "email": {
            "subject": "Lembrete: agendamento amanhã em {{tenant_name}}",
            "body": (
                "Oi {{customer_name}}, passando pra lembrar do seu agendamento "
                "amanhã ({{appointment_date}} às {{appointment_time}}) "
                "com {{professional_name}}.\n\nTe esperamos!"
            ),
        },
        "sms": {
            "body": (
                "Lembrete: amanhã às {{appointment_time}} agendamento em "
                "{{tenant_name}} com {{professional_name}}."
            ),
        },
        "whatsapp": {
            "body": (
                "⏰ Lembrete!\nOlá {{customer_name}}, amanhã ({{appointment_date}} "
                "às {{appointment_time}}) você tem agendamento em *{{tenant_name}}*."
            ),
        },
    },
    "tenant_welcome": {
        "email": {
            "subject": "Bem-vindo à AUTOMIC, {{owner_name}}!",
            "body": (
                "Olá {{owner_name}}!\n\nSeu cadastro em {{tenant_name}} foi criado. "
                "Você tem {{trial_days_left}} dias de trial.\n\n"
                "Acesse: https://app.automic.tech/{{tenant_slug}}"
            ),
        },
    },
    "invoice_due_3d": {
        "email": {
            "subject": "Sua fatura AUTOMIC vence em 3 dias",
            "body": (
                "Olá {{owner_name}},\n\nSua fatura de R$ {{invoice_amount}} "
                "vence em {{invoice_due_date}}.\nPague pelo painel."
            ),
        },
    },
    "invoice_overdue": {
        "email": {
            "subject": "Fatura AUTOMIC em atraso",
            "body": (
                "Olá {{owner_name}},\n\nSua fatura de R$ {{invoice_amount}} "
                "venceu em {{invoice_due_date}} e ainda não consta como paga. "
                "Por favor, regularize para evitar suspensão automática."
            ),
        },
    },
    "invoice_paid": {
        "email": {
            "subject": "Recebemos seu pagamento — AUTOMIC",
            "body": (
                "Olá {{owner_name}},\n\nConfirmamos o pagamento da fatura "
                "de R$ {{invoice_amount}}. Obrigado!"
            ),
        },
    },
    "appointment_cancelled_bulk": {
        "whatsapp": {
            "body": (
                "Olá {{customer_name}}!\n"
                "Precisamos cancelar seu agendamento em *{{tenant_name}}* "
                "marcado para {{appointment_date}}.\n"
                "Motivo: {{reason}}\n"
                "Pedimos desculpas — entre em contato para reagendar."
            ),
        },
        "email": {
            "subject": "Cancelamento de agendamento — {{tenant_name}}",
            "body": (
                "Olá {{customer_name}},\n\n"
                "Precisamos cancelar seu agendamento marcado para "
                "{{appointment_date}}.\n"
                "Motivo: {{reason}}\n\n"
                "Por favor entre em contato para reagendar. "
                "Pedimos sinceras desculpas pelo transtorno."
            ),
        },
    },
}


notification_service = NotificationService()
