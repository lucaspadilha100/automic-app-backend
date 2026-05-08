from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.term import TenantTerm, CustomerTermAcceptance, TermType
from app.models.customer import TenantCustomer
from app.core.exceptions import NotFoundError, ForbiddenError
from app.services.audit_service import audit_service
from app.services.customer_event_service import customer_event_service


class TermService:

    # ---- Administrative ----

    def list_terms(
        self,
        db: Session,
        tenant_id: UUID,
        term_type: Optional[TermType] = None,
        is_active: Optional[bool] = None,
    ) -> List[TenantTerm]:
        q = db.query(TenantTerm).filter(TenantTerm.tenant_id == tenant_id)
        if term_type is not None:
            q = q.filter(TenantTerm.term_type == term_type)
        if is_active is not None:
            q = q.filter(TenantTerm.is_active == is_active)
        return q.order_by(TenantTerm.created_at.desc()).all()

    def get_term(self, db: Session, tenant_id: UUID, term_id: UUID) -> TenantTerm:
        term = (
            db.query(TenantTerm)
            .filter(TenantTerm.id == term_id, TenantTerm.tenant_id == tenant_id)
            .first()
        )
        if not term:
            raise NotFoundError("Termo não encontrado.")
        return term

    def create_term(
        self,
        db: Session,
        tenant_id: UUID,
        data: dict,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> TenantTerm:
        term = TenantTerm(tenant_id=tenant_id, **data)
        db.add(term)
        db.flush()
        audit_service.log(
            db=db,
            action="term_created",
            entity_type="tenant_term",
            entity_id=term.id,
            tenant_id=tenant_id,
            user_id=user_id,
            new_values={
                "title": term.title,
                "term_type": term.term_type.value,
                "version": term.version,
                "is_active": term.is_active,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.commit()
        db.refresh(term)
        return term

    def update_term(
        self,
        db: Session,
        tenant_id: UUID,
        term_id: UUID,
        data: dict,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> TenantTerm:
        term = self.get_term(db, tenant_id, term_id)
        old_values = {
            "title": term.title,
            "content": term.content,
            "term_type": term.term_type.value,
            "version": term.version,
            "is_active": term.is_active,
        }
        for field, value in data.items():
            if value is not None:
                setattr(term, field, value)
        db.flush()
        audit_service.log(
            db=db,
            action="term_updated",
            entity_type="tenant_term",
            entity_id=term.id,
            tenant_id=tenant_id,
            user_id=user_id,
            old_values=old_values,
            new_values={
                "title": term.title,
                "term_type": term.term_type.value,
                "version": term.version,
                "is_active": term.is_active,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.commit()
        db.refresh(term)
        return term

    def set_term_status(
        self,
        db: Session,
        tenant_id: UUID,
        term_id: UUID,
        is_active: bool,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> TenantTerm:
        term = self.get_term(db, tenant_id, term_id)
        old_status = term.is_active
        term.is_active = is_active
        db.flush()
        action = "term_activated" if is_active else "term_deactivated"
        audit_service.log(
            db=db,
            action=action,
            entity_type="tenant_term",
            entity_id=term.id,
            tenant_id=tenant_id,
            user_id=user_id,
            old_values={"is_active": old_status},
            new_values={"is_active": is_active},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.commit()
        db.refresh(term)
        return term

    # ---- Customer ----

    def list_active_terms_for_customer(
        self,
        db: Session,
        tenant_id: UUID,
    ) -> List[TenantTerm]:
        return (
            db.query(TenantTerm)
            .filter(TenantTerm.tenant_id == tenant_id, TenantTerm.is_active == True)
            .order_by(TenantTerm.created_at.asc())
            .all()
        )

    def accept_term(
        self,
        db: Session,
        tenant_id: UUID,
        term_id: UUID,
        customer_account_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> CustomerTermAcceptance:
        term = (
            db.query(TenantTerm)
            .filter(TenantTerm.id == term_id)
            .first()
        )
        if not term:
            raise NotFoundError("Termo não encontrado.")

        if str(term.tenant_id) != str(tenant_id):
            raise ForbiddenError("Termo não pertence a este tenant.")

        if not term.is_active:
            raise ForbiddenError("Não é possível aceitar um termo inativo.")

        tenant_customer = (
            db.query(TenantCustomer)
            .filter(
                TenantCustomer.tenant_id == tenant_id,
                TenantCustomer.customer_account_id == customer_account_id,
            )
            .first()
        )

        now = datetime.now(timezone.utc)
        acceptance = CustomerTermAcceptance(
            tenant_id=tenant_id,
            customer_account_id=customer_account_id,
            tenant_customer_id=tenant_customer.id if tenant_customer else None,
            term_id=term_id,
            accepted_at=now,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=now,
        )
        db.add(acceptance)
        db.flush()

        customer_event_service.emit(
            db=db,
            event_type="term_accepted",
            tenant_id=tenant_id,
            customer_account_id=customer_account_id,
            tenant_customer_id=tenant_customer.id if tenant_customer else None,
            entity_type="tenant_term",
            entity_id=term_id,
            metadata={
                "term_type": term.term_type.value,
                "version": term.version,
                "title": term.title,
            },
        )

        db.commit()
        db.refresh(acceptance)
        return acceptance


term_service = TermService()
