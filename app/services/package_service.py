from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.package import CustomerPackage, PackageSession, PackageService as PackageServiceModel
from app.models.tenant import Tenant
from app.core.exceptions import (
    CustomerPackageNotFoundError, PackageExpiredError,
    PackageCancelledError, PackageNoRemainingSessionsError,
    PackageServiceNotAllowedError, PackagePaymentPendingError,
    FeatureDisabledError,
)


class PackageService:

    def validate_package_use(
        self, db: Session, tenant: Tenant,
        customer_package_id: UUID, service_ids: List[UUID],
    ) -> CustomerPackage:
        cp = (
            db.query(CustomerPackage)
            .filter(CustomerPackage.id == customer_package_id, CustomerPackage.tenant_id == tenant.id)
            .first()
        )
        if not cp:
            raise CustomerPackageNotFoundError()

        if cp.status == "cancelled":
            raise PackageCancelledError()

        if cp.status == "expired":
            raise PackageExpiredError()

        if cp.expires_at and datetime.now(timezone.utc) > cp.expires_at:
            cp.status = "expired"
            raise PackageExpiredError()

        if cp.remaining_sessions <= 0:
            raise PackageNoRemainingSessionsError()

        if cp.payment_status == "pending":
            raise PackagePaymentPendingError()

        # Validate allowed services. Prefer relational package_services, fallback to legacy JSONB service_ids.
        links = db.query(PackageServiceModel).filter(
            PackageServiceModel.tenant_id == tenant.id,
            PackageServiceModel.package_id == cp.package_id,
        ).all()
        if links:
            allowed = {str(link.service_id) for link in links}
        else:
            pkg = cp.package
            allowed = set(str(sid) for sid in (pkg.service_ids or []))
        if allowed:
            for sid in service_ids:
                if str(sid) not in allowed:
                    raise PackageServiceNotAllowedError()

        return cp

    def reserve_session(
        self, db: Session, tenant_id: UUID,
        customer_package_id: UUID, appointment_id: UUID,
        service_id: Optional[UUID] = None,
    ) -> PackageSession:
        cp = db.query(CustomerPackage).filter(CustomerPackage.id == customer_package_id).with_for_update().first()
        if not cp:
            raise CustomerPackageNotFoundError()

        cp.remaining_sessions -= 1

        session = PackageSession(
            tenant_id=tenant_id,
            customer_package_id=customer_package_id,
            appointment_id=appointment_id,
            service_id=service_id,
            action="reserved",
            status="reserved",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.flush()
        return session

    def consume_session(
        self, db: Session, tenant_id: UUID,
        customer_package_id: UUID, appointment_id: UUID,
    ) -> None:
        cp = db.query(CustomerPackage).filter(CustomerPackage.id == customer_package_id).with_for_update().first()
        if not cp:
            return

        cp.used_sessions += 1

        # Mark the reserved session as consumed
        session = (
            db.query(PackageSession)
            .filter(
                PackageSession.customer_package_id == customer_package_id,
                PackageSession.appointment_id == appointment_id,
                PackageSession.action == "reserved",
            )
            .first()
        )
        if session:
            session.action = "consumed"
            session.status = "used"
            session.updated_at = datetime.now(timezone.utc)

        # Check if fully used
        if cp.used_sessions >= cp.total_sessions:
            cp.status = "fully_used"

    def return_session(
        self, db: Session, tenant_id: UUID,
        customer_package_id: UUID, appointment_id: UUID,
    ) -> None:
        cp = db.query(CustomerPackage).filter(CustomerPackage.id == customer_package_id).with_for_update().first()
        if not cp:
            return

        # Only return if session was reserved (not yet consumed)
        session = (
            db.query(PackageSession)
            .filter(
                PackageSession.customer_package_id == customer_package_id,
                PackageSession.appointment_id == appointment_id,
                PackageSession.action == "reserved",
            )
            .first()
        )
        if session:
            session.action = "returned"
            session.status = "cancelled"
            session.updated_at = datetime.now(timezone.utc)
            cp.remaining_sessions += 1

            # Reactivate if was fully used
            if cp.status in ("completed", "fully_used"):
                cp.status = "active"


package_service = PackageService()
