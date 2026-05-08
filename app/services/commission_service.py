from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.commission import (
    ProfessionalCommissionSetting, CommissionRecord,
    CommissionType, CommissionStatus,
)
from app.models.appointment import Appointment
from app.models.professional import Professional
from app.core.exceptions import NotFoundError, ValidationError
from app.services.audit_service import audit_service


class CommissionService:

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _get_setting(self, db: Session, tenant_id: UUID, setting_id: UUID) -> ProfessionalCommissionSetting:
        s = db.query(ProfessionalCommissionSetting).filter(
            ProfessionalCommissionSetting.id == setting_id,
            ProfessionalCommissionSetting.tenant_id == tenant_id,
        ).first()
        if not s:
            raise NotFoundError("Configuração de comissão não encontrada.")
        return s

    def _get_record(self, db: Session, tenant_id: UUID, record_id: UUID) -> CommissionRecord:
        r = db.query(CommissionRecord).filter(
            CommissionRecord.id == record_id,
            CommissionRecord.tenant_id == tenant_id,
        ).first()
        if not r:
            raise NotFoundError("Registro de comissão não encontrado.")
        return r

    def _validate_professional(self, db: Session, tenant_id: UUID, professional_id: UUID) -> None:
        p = db.query(Professional).filter(
            Professional.id == professional_id,
            Professional.tenant_id == tenant_id,
        ).first()
        if not p:
            raise NotFoundError("Profissional não encontrado neste tenant.")

    def _calculate_amount(
        self,
        commission_type: CommissionType,
        commission_value: Decimal,
        base_amount: Decimal,
    ) -> Decimal:
        if commission_type == CommissionType.percentage:
            return (base_amount * commission_value / Decimal("100")).quantize(Decimal("0.01"))
        if commission_type == CommissionType.fixed:
            return commission_value.quantize(Decimal("0.01"))
        return Decimal("0")

    # ── Settings ───────────────────────────────────────────────────────────────

    def list_settings(self, db: Session, tenant_id: UUID) -> List[ProfessionalCommissionSetting]:
        return (
            db.query(ProfessionalCommissionSetting)
            .filter(ProfessionalCommissionSetting.tenant_id == tenant_id)
            .order_by(ProfessionalCommissionSetting.created_at.desc())
            .all()
        )

    def get_setting(self, db: Session, tenant_id: UUID, setting_id: UUID) -> ProfessionalCommissionSetting:
        return self._get_setting(db, tenant_id, setting_id)

    def create_setting(
        self,
        db: Session,
        tenant_id: UUID,
        data: dict,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ProfessionalCommissionSetting:
        self._validate_professional(db, tenant_id, data["professional_id"])

        if data.get("commission_type") == CommissionType.percentage:
            val = Decimal(str(data.get("commission_value", 0)))
            if val > 100:
                raise ValidationError("Percentual não pode ultrapassar 100.")

        setting = ProfessionalCommissionSetting(tenant_id=tenant_id, **data)
        db.add(setting)
        db.flush()

        audit_service.log(
            db=db,
            action="commission_setting_created",
            entity_type="professional_commission_setting",
            entity_id=setting.id,
            tenant_id=tenant_id,
            user_id=user_id,
            new_values={
                "professional_id": str(data["professional_id"]),
                "commission_type": str(data.get("commission_type")),
                "commission_value": str(data.get("commission_value", 0)),
                "is_active": data.get("is_active", True),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.commit()
        db.refresh(setting)
        return setting

    def update_setting(
        self,
        db: Session,
        tenant_id: UUID,
        setting_id: UUID,
        data: dict,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ProfessionalCommissionSetting:
        setting = self._get_setting(db, tenant_id, setting_id)
        old_values = {
            "commission_type": setting.commission_type.value,
            "commission_value": str(setting.commission_value),
            "is_active": setting.is_active,
        }

        new_type = data.get("commission_type", setting.commission_type)
        new_val = Decimal(str(data.get("commission_value", setting.commission_value)))
        if new_type == CommissionType.percentage and new_val > 100:
            raise ValidationError("Percentual não pode ultrapassar 100.")
        if new_val < 0:
            raise ValidationError("commission_value não pode ser negativo.")

        for field, value in data.items():
            if value is not None:
                setattr(setting, field, value)

        db.flush()
        audit_service.log(
            db=db,
            action="commission_setting_updated",
            entity_type="professional_commission_setting",
            entity_id=setting.id,
            tenant_id=tenant_id,
            user_id=user_id,
            old_values=old_values,
            new_values={
                "commission_type": setting.commission_type.value,
                "commission_value": str(setting.commission_value),
                "is_active": setting.is_active,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.commit()
        db.refresh(setting)
        return setting

    def set_setting_status(
        self,
        db: Session,
        tenant_id: UUID,
        setting_id: UUID,
        is_active: bool,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ProfessionalCommissionSetting:
        setting = self._get_setting(db, tenant_id, setting_id)
        old = setting.is_active
        setting.is_active = is_active
        db.flush()
        action = "commission_setting_activated" if is_active else "commission_setting_deactivated"
        audit_service.log(
            db=db,
            action=action,
            entity_type="professional_commission_setting",
            entity_id=setting.id,
            tenant_id=tenant_id,
            user_id=user_id,
            old_values={"is_active": old},
            new_values={"is_active": is_active},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.commit()
        db.refresh(setting)
        return setting

    # ── Records ────────────────────────────────────────────────────────────────

    def list_records(
        self,
        db: Session,
        tenant_id: UUID,
        professional_id: Optional[UUID] = None,
        status: Optional[CommissionStatus] = None,
    ) -> List[CommissionRecord]:
        q = db.query(CommissionRecord).filter(CommissionRecord.tenant_id == tenant_id)
        if professional_id:
            q = q.filter(CommissionRecord.professional_id == professional_id)
        if status:
            q = q.filter(CommissionRecord.status == status)
        return q.order_by(CommissionRecord.created_at.desc()).all()

    def get_record(self, db: Session, tenant_id: UUID, record_id: UUID) -> CommissionRecord:
        return self._get_record(db, tenant_id, record_id)

    def mark_paid(
        self,
        db: Session,
        tenant_id: UUID,
        record_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> CommissionRecord:
        record = self._get_record(db, tenant_id, record_id)
        if record.status != CommissionStatus.pending:
            raise ValidationError("Apenas comissões pendentes podem ser marcadas como pagas.")
        old_status = record.status
        record.status = CommissionStatus.paid
        db.flush()
        audit_service.log(
            db=db,
            action="commission_marked_paid",
            entity_type="commission_record",
            entity_id=record.id,
            tenant_id=tenant_id,
            user_id=user_id,
            old_values={"status": old_status.value},
            new_values={"status": CommissionStatus.paid.value},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.commit()
        db.refresh(record)
        return record

    def cancel_record(
        self,
        db: Session,
        tenant_id: UUID,
        record_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> CommissionRecord:
        record = self._get_record(db, tenant_id, record_id)
        if record.status == CommissionStatus.cancelled:
            raise ValidationError("Comissão já está cancelada.")
        old_status = record.status
        record.status = CommissionStatus.cancelled
        db.flush()
        audit_service.log(
            db=db,
            action="commission_cancelled",
            entity_type="commission_record",
            entity_id=record.id,
            tenant_id=tenant_id,
            user_id=user_id,
            old_values={"status": old_status.value},
            new_values={"status": CommissionStatus.cancelled.value},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.commit()
        db.refresh(record)
        return record

    # ── Auto-generation ────────────────────────────────────────────────────────

    def generate_for_appointment(self, db: Session, appointment: Appointment) -> Optional[CommissionRecord]:
        """
        Called after appointment is marked completed.
        Does not commit — caller owns the transaction.
        Returns None if no commission should be generated.
        """
        if not appointment.professional_id:
            return None

        # Idempotency guard: skip if record already exists
        existing = db.query(CommissionRecord).filter(
            CommissionRecord.appointment_id == appointment.id,
            CommissionRecord.professional_id == appointment.professional_id,
            CommissionRecord.tenant_id == appointment.tenant_id,
        ).first()
        if existing:
            return existing

        setting = db.query(ProfessionalCommissionSetting).filter(
            ProfessionalCommissionSetting.tenant_id == appointment.tenant_id,
            ProfessionalCommissionSetting.professional_id == appointment.professional_id,
            ProfessionalCommissionSetting.is_active == True,
        ).first()

        if not setting:
            return None

        if setting.commission_type == CommissionType.none:
            return None

        base_amount = Decimal(str(appointment.total_price or 0))
        commission_value = Decimal(str(setting.commission_value))
        commission_amount = self._calculate_amount(setting.commission_type, commission_value, base_amount)

        record = CommissionRecord(
            tenant_id=appointment.tenant_id,
            appointment_id=appointment.id,
            professional_id=appointment.professional_id,
            base_amount=base_amount,
            commission_type=setting.commission_type,
            commission_value=commission_value,
            commission_amount=commission_amount,
            status=CommissionStatus.pending,
        )
        db.add(record)
        db.flush()
        return record


commission_service = CommissionService()
