from sqlalchemy.orm import Session
from app.models.tenant import Tenant, TenantPaymentSettings


class PaymentService:
    def get_or_create_settings(self, db: Session, tenant: Tenant) -> TenantPaymentSettings:
        settings = db.query(TenantPaymentSettings).filter(TenantPaymentSettings.tenant_id == tenant.id).first()
        if not settings:
            settings = TenantPaymentSettings(tenant_id=tenant.id)
            db.add(settings)
            db.flush()
        return settings


payment_service = PaymentService()
