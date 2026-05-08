from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.tenant import Tenant


class TenantRepository:
    """Repository helpers for tenants. Master-scoped by id, not tenant_id."""

    def get_by_id(self, db: Session, tenant_id: UUID, entity_id: Optional[UUID] = None) -> Optional[Tenant]:
        target_id = entity_id or tenant_id
        return db.query(Tenant).filter(Tenant.id == target_id, Tenant.deleted_at.is_(None)).first()

    def list_by_tenant(self, db: Session, tenant_id: UUID, skip: int = 0, limit: int = 100) -> List[Tenant]:
        tenant = self.get_by_id(db, tenant_id)
        return [tenant] if tenant else []


repository = TenantRepository()
