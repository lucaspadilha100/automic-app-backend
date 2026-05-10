from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid

from db.session import get_db
from app.core.dependencies import (
    get_current_user, require_active_tenant, require_receptionist_or_above,
    require_manager_or_above,
)
from app.core.exceptions import NotFoundError, AppError
from app.models.user import User
from app.models.tenant import Tenant
from app.models.appointment import Appointment
from app.models.payment import Payment
from app.services.audit_service import audit_service
from app.services.customer_event_service import customer_event_service

router = APIRouter(prefix="/payments", tags=["Pagamentos"])


def _get_appointment(appointment_id: uuid.UUID, tenant: Tenant, db: Session) -> Appointment:
    appt = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.tenant_id == tenant.id,
    ).first()
    if not appt:
        raise NotFoundError("APPOINTMENT_NOT_FOUND", "Agendamento não encontrado.")
    return appt


@router.post("/appointments/{appointment_id}/payments")
def register_payment(
    appointment_id: uuid.UUID,
    amount: float,
    payment_method: str = "cash",
    provider: Optional[str] = None,
    provider_payment_id: Optional[str] = None,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    """Registra um pagamento manual ou confirma pagamento de gateway."""
    appt = _get_appointment(appointment_id, tenant, db)

    payment = Payment(
        tenant_id=tenant.id,
        appointment_id=appt.id,
        customer_account_id=appt.customer_account_id,
        registered_by_user_id=current_user.id,
        amount=amount,
        status="paid",
        payment_method=payment_method,
        provider=provider,
        provider_payment_id=provider_payment_id,
        paid_at=datetime.now(timezone.utc),
    )
    db.add(payment)

    # Atualizar status de pagamento do agendamento
    appt.payment_status = "paid"

    # Auto-confirmar agendamento se estava pendente
    if appt.status in ("pending_payment", "scheduled"):
        from app.services.appointment_service import appointment_service
        appointment_service.confirm(db, appt, current_user.id)

    audit_service.log(
        db=db, action="payment_registered",
        entity_type="payment", entity_id=payment.id,
        tenant_id=tenant.id, user_id=current_user.id,
        customer_account_id=appt.customer_account_id,
        new_values={"amount": amount, "method": payment_method},
    )

    customer_event_service.emit(
        db=db, event_type="payment_created",
        tenant_id=tenant.id,
        customer_account_id=appt.customer_account_id,
        tenant_customer_id=appt.tenant_customer_id,
        entity_type="payment", entity_id=payment.id,
    )

    customer_event_service.emit(
        db=db, event_type="payment_confirmed",
        tenant_id=tenant.id,
        customer_account_id=appt.customer_account_id,
        tenant_customer_id=appt.tenant_customer_id,
        entity_type="appointment", entity_id=appt.id,
    )

    db.commit()
    db.refresh(payment)
    return {
        "id": str(payment.id),
        "amount": float(payment.amount),
        "status": payment.status,
        "payment_method": payment.payment_method,
        "paid_at": payment.paid_at.isoformat(),
    }


@router.post("/appointments/{appointment_id}/payments/{payment_id}/refund")
def refund_payment(
    appointment_id: uuid.UUID,
    payment_id: uuid.UUID,
    reason: Optional[str] = None,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    """Estorna um pagamento."""
    appt = _get_appointment(appointment_id, tenant, db)

    payment = db.query(Payment).filter(
        Payment.id == payment_id,
        Payment.appointment_id == appt.id,
        Payment.tenant_id == tenant.id,
    ).first()
    if not payment:
        raise NotFoundError("PAYMENT_NOT_FOUND", "Pagamento não encontrado.")

    if payment.status != "paid":
        raise AppError(
            "PAYMENT_NOT_REFUNDABLE",
            f"Pagamentos com status '{payment.status}' não podem ser estornados.",
            422,
        )

    payment.status = "refunded"
    appt.payment_status = "refunded"

    audit_service.log(
        db=db, action="payment_refunded",
        entity_type="payment", entity_id=payment.id,
        tenant_id=tenant.id, user_id=current_user.id,
        old_values={"status": "paid"},
        new_values={"status": "refunded", "reason": reason},
    )
    db.commit()
    return {"message": "Pagamento estornado.", "payment_id": str(payment.id)}


@router.get("/appointments/{appointment_id}/payments")
def list_payments(
    appointment_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista todos os pagamentos de um agendamento."""
    appt = _get_appointment(appointment_id, tenant, db)
    return [
        {
            "id": str(p.id),
            "amount": float(p.amount),
            "status": p.status,
            "payment_method": p.payment_method,
            "provider": p.provider,
            "paid_at": p.paid_at.isoformat() if p.paid_at else None,
        }
        for p in appt.payments
    ]


@router.get("")
def list_payments_all(
    date: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 200,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_receptionist_or_above),
    db: Session = Depends(get_db),
):
    """Lista pagamentos detalhados do tenant. Por padrão retorna o dia atual."""
    from datetime import date as date_type, timedelta
    from sqlalchemy.orm import joinedload

    q = db.query(Payment).options(
        joinedload(Payment.customer_account),
        joinedload(Payment.registered_by),
        joinedload(Payment.appointment),
    ).filter(Payment.tenant_id == tenant.id)

    if date:
        day = date_type.fromisoformat(date)
        start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        q = q.filter(Payment.paid_at >= start, Payment.paid_at < end)
    elif date_from or date_to:
        if date_from:
            d = date_type.fromisoformat(date_from)
            q = q.filter(Payment.paid_at >= datetime(d.year, d.month, d.day, tzinfo=timezone.utc))
        if date_to:
            d = date_type.fromisoformat(date_to)
            q = q.filter(Payment.paid_at < datetime(d.year, d.month, d.day, tzinfo=timezone.utc) + timedelta(days=1))
    else:
        today = date_type.today()
        start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
        q = q.filter(Payment.paid_at >= start, Payment.paid_at < start + timedelta(days=1))

    if status:
        q = q.filter(Payment.status == status)

    payments = q.order_by(Payment.paid_at.desc()).offset(skip).limit(limit).all()

    result = []
    for p in payments:
        appt = p.appointment
        service_name = None
        if appt and appt.appointment_services:
            service_name = appt.appointment_services[0].service_name_snapshot

        registered_by = p.registered_by
        registered_by_role = registered_by.role if registered_by else None

        result.append({
            "id": str(p.id),
            "amount": float(p.amount),
            "status": p.status,
            "payment_method": p.payment_method,
            "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            "customer_name": p.customer_account.name if p.customer_account else None,
            "service_name": service_name,
            "appointment_id": str(p.appointment_id),
            "registered_by_name": registered_by.name if registered_by else None,
            "registered_by_role": registered_by_role,
        })

    return result


@router.get("/summary")
def payment_summary(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    """Resumo de pagamentos por método."""
    from sqlalchemy import func

    q = db.query(
        Payment.payment_method,
        Payment.status,
        func.count(Payment.id).label("count"),
        func.sum(Payment.amount).label("total"),
    ).filter(Payment.tenant_id == tenant.id)

    if date_from:
        q = q.filter(Payment.created_at >= date_from)
    if date_to:
        q = q.filter(Payment.created_at <= date_to)

    rows = q.group_by(Payment.payment_method, Payment.status).all()
    return [
        {
            "payment_method": r.payment_method,
            "status": r.status,
            "count": r.count,
            "total": float(r.total or 0),
        }
        for r in rows
    ]
