"""
Reminder service — sends 24h appointment reminders.

Sweep logic: pick all confirmed appointments whose start_datetime is in the
window [now+23h, now+25h]. For each, send a reminder via the channel(s)
configured for the tenant (default: WhatsApp + email if customer has email).

Idempotent — uses NotificationLog with event_type='appointment_reminder_24h'
to skip re-sends.

Designed to run hourly. The window of 2h covers any drift in scheduling.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
import logging

import pytz
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.tenant import Tenant
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)


class ReminderService:
    def send_24h_reminders(self, db: Session) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        window_start = now + timedelta(hours=23)
        window_end = now + timedelta(hours=25)

        appts: List[Appointment] = (
            db.query(Appointment)
            .filter(
                Appointment.start_datetime >= window_start,
                Appointment.start_datetime < window_end,
                Appointment.status.in_(("scheduled", "confirmed")),
            )
            .all()
        )

        sent_email = 0
        sent_whatsapp = 0
        sent_sms = 0
        skipped = 0
        failed = 0

        for appt in appts:
            customer = appt.customer_account
            if not customer:
                skipped += 1
                continue

            tenant = appt.tenant
            tz_name = tenant.timezone or "America/Sao_Paulo"
            try:
                tz = pytz.timezone(tz_name)
            except Exception:
                tz = pytz.timezone("America/Sao_Paulo")
            start_local = appt.start_datetime.astimezone(tz)

            prof = appt.professional
            services = appt.appointment_services or []
            service_names = ", ".join(getattr(s, "service_name_snapshot", "") for s in services)

            context = {
                "customer_name": customer.name or "",
                "professional_name": prof.name if prof else "",
                "service_name": service_names,
                "appointment_date": start_local.strftime("%d/%m/%Y"),
                "appointment_time": start_local.strftime("%H:%M"),
                "tenant_name": tenant.public_name or tenant.name,
            }

            # Try WhatsApp first if phone present (most engaged channel for clinics)
            if customer.phone:
                log = notification_service.send_generic(
                    db, tenant_id=tenant.id, channel="whatsapp",
                    event_type="appointment_reminder_24h",
                    to=customer.phone, context=context,
                    appointment_id=appt.id,
                    customer_account_id=customer.id,
                    skip_if_already_sent=True,
                )
                if log.status == "sent":
                    sent_whatsapp += 1
                elif log.status == "failed":
                    failed += 1

            # Email as backup if customer has email
            if customer.email:
                log = notification_service.send_generic(
                    db, tenant_id=tenant.id, channel="email",
                    event_type="appointment_reminder_24h",
                    to=customer.email, context=context,
                    appointment_id=appt.id,
                    customer_account_id=customer.id,
                    skip_if_already_sent=True,
                )
                if log.status == "sent":
                    sent_email += 1
                elif log.status == "failed":
                    failed += 1

        return {
            "checked_at": now.isoformat(),
            "appointments_in_window": len(appts),
            "sent_whatsapp": sent_whatsapp,
            "sent_email": sent_email,
            "sent_sms": sent_sms,
            "skipped": skipped,
            "failed": failed,
        }


reminder_service = ReminderService()
