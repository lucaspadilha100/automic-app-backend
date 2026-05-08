from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.service import Service


class ServiceRepository:
    """Small repository with tenant-safe helpers for Service."""

    model = Service

    def get_by_id(self, db: Session, tenant_id: UUID, entity_id: UUID) -> Optional[Service]:
        return db.query(self.model).filter(self.model.id == entity_id, self.model.tenant_id == tenant_id).first()

    def list_by_tenant(self, db: Session, tenant_id: UUID, skip: int = 0, limit: int = 100) -> List[Service]:
        return db.query(self.model).filter(self.model.tenant_id == tenant_id).offset(skip).limit(limit).all()


repository = ServiceRepository()
