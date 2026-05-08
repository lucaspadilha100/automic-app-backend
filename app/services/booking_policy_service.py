from sqlalchemy.orm import Session
from app.models.tenant import TenantBookingPolicy


class BookingPolicyService:
    def get_or_create(self, db: Session, tenant_id):
        policy = db.query(TenantBookingPolicy).filter(TenantBookingPolicy.tenant_id == tenant_id).first()
        if not policy:
            policy = TenantBookingPolicy(tenant_id=tenant_id)
            db.add(policy)
            db.flush()
        return policy


booking_policy_service = BookingPolicyService()
