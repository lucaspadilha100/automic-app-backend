"""
ScheduleException — time windows where appointments cannot be booked.

Three flavors via `exception_type`:
  - holiday   : feriado nacional/local — bloqueia toda a clínica/unidade.
                professional_id e unit_id ficam null.
  - leave     : folga/férias de um profissional específico.
                professional_id obrigatório.
  - closure   : clínica fechada por manutenção, evento, etc.
                Pode ser por unit_id ou tenant inteiro.

Quando criar ou reagendar agendamento, o serviço checa se o horário
solicitado intersecta uma ScheduleException ativa. Se sim, rejeita.

A exceção tem [start_datetime, end_datetime). Inclusiva no início,
exclusiva no fim — segue convenção padrão de intervalos.

Idempotência por unique key: (tenant_id, professional_id, start_datetime,
end_datetime, exception_type) — tentativas duplicadas não criam dois.
"""
from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey, CheckConstraint, Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.base import Base
from app.models.base_model import UUIDPrimaryKey, TimestampMixin


class ScheduleException(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "schedule_exceptions"

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # If set, only this professional is blocked.
    # If null, applies to ALL professionals (whole tenant or unit).
    professional_id = Column(
        UUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )

    # If set, only this unit is blocked. Null = all units.
    unit_id = Column(
        UUID(as_uuid=True),
        ForeignKey("units.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )

    start_datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    end_datetime = Column(DateTime(timezone=True), nullable=False, index=True)

    exception_type = Column(String(20), nullable=False)  # holiday | leave | closure
    reason = Column(Text, nullable=True)

    # Audit
    created_by_user_id = Column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "exception_type IN ('holiday','leave','closure')",
            name="ck_schedule_exceptions_type",
        ),
        CheckConstraint(
            "end_datetime > start_datetime",
            name="ck_schedule_exceptions_range",
        ),
        Index("ix_schedule_exceptions_window", "tenant_id", "start_datetime", "end_datetime"),
        Index(
            "ix_schedule_exceptions_prof_window",
            "professional_id", "start_datetime", "end_datetime",
        ),
    )
