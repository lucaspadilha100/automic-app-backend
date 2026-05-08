from sqlalchemy.orm import Session

from app.models.customer import CustomerNote, TenantCustomer
from app.models.procedure import ProcedureHistory
from app.models.event import CustomerEvent


class CustomerTimelineService:
    """Aggregates a tenant customer's visible/internal timeline safely."""

    def list_notes(self, db: Session, tenant_id, tenant_customer_id, include_internal: bool = True):
        q = db.query(CustomerNote).filter(CustomerNote.tenant_id == tenant_id, CustomerNote.tenant_customer_id == tenant_customer_id)
        if not include_internal:
            q = q.filter(CustomerNote.visibility == "customer_visible")
        return q.order_by(CustomerNote.created_at.desc()).all()

    def list_public_procedures(self, db: Session, tenant_id, customer_account_id):
        return db.query(ProcedureHistory).filter(
            ProcedureHistory.tenant_id == tenant_id,
            ProcedureHistory.customer_account_id == customer_account_id,
        ).order_by(ProcedureHistory.procedure_date.desc()).all()

    def list_events(self, db: Session, tenant_id, tenant_customer_id):
        return db.query(CustomerEvent).filter(
            CustomerEvent.tenant_id == tenant_id,
            CustomerEvent.tenant_customer_id == tenant_customer_id,
        ).order_by(CustomerEvent.created_at.desc()).all()

    def get_tenant_customer(self, db: Session, tenant_id, tenant_customer_id):
        return db.query(TenantCustomer).filter(TenantCustomer.tenant_id == tenant_id, TenantCustomer.id == tenant_customer_id).first()


customer_timeline_service = CustomerTimelineService()
