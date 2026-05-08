from sqlalchemy.orm import Session

from app.core.exceptions import UnitNotFoundError, ValidationError
from app.models.unit import Unit


class UnitService:
    """Unit/branch business rules, including mandatory main unit."""

    def get_main_unit(self, db: Session, tenant_id):
        return db.query(Unit).filter(
            Unit.tenant_id == tenant_id,
            Unit.is_main == True,
            Unit.deleted_at.is_(None),
        ).first()

    def ensure_main_unit(self, db: Session, tenant, flush: bool = True) -> Unit:
        unit = self.get_main_unit(db, tenant.id)
        if unit:
            return unit
        unit = Unit(
            tenant_id=tenant.id,
            name=tenant.public_name or tenant.name,
            address=tenant.address,
            phone=tenant.phone,
            whatsapp=tenant.whatsapp,
            email=tenant.email,
            timezone=tenant.timezone,
            is_main=True,
            is_active=True,
        )
        db.add(unit)
        if flush:
            db.flush()
        return unit

    def count_active(self, db: Session, tenant_id) -> int:
        return db.query(Unit).filter(Unit.tenant_id == tenant_id, Unit.deleted_at.is_(None)).count()

    def get_for_tenant(self, db: Session, tenant_id, unit_id) -> Unit:
        unit = db.query(Unit).filter(Unit.id == unit_id, Unit.tenant_id == tenant_id, Unit.deleted_at.is_(None)).first()
        if not unit:
            raise UnitNotFoundError()
        return unit

    def prevent_main_deletion(self, unit: Unit) -> None:
        if unit.is_main:
            raise ValidationError("Não é possível remover a unidade principal.")


unit_service = UnitService()
