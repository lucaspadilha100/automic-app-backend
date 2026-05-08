from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.procedure_photo import ProcedurePhoto, PhotoType, PhotoVisibility
from app.models.procedure import ProcedureHistory
from app.models.media import MediaFile
from app.models.service import Service
from app.core.exceptions import NotFoundError, ForbiddenError
from app.services.audit_service import audit_service
from app.services.customer_event_service import customer_event_service


class ProcedurePhotoService:

    def _get_procedure(self, db: Session, tenant_id: UUID, procedure_id: UUID) -> ProcedureHistory:
        ph = (
            db.query(ProcedureHistory)
            .filter(ProcedureHistory.id == procedure_id, ProcedureHistory.tenant_id == tenant_id)
            .first()
        )
        if not ph:
            raise NotFoundError("Histórico de procedimento não encontrado.")
        return ph

    def _get_media_file(self, db: Session, tenant_id: UUID, media_file_id: UUID) -> MediaFile:
        mf = (
            db.query(MediaFile)
            .filter(MediaFile.id == media_file_id, MediaFile.tenant_id == tenant_id)
            .first()
        )
        if not mf:
            raise NotFoundError("Arquivo de mídia não encontrado neste tenant.")
        return mf

    def _validate_service(self, db: Session, tenant_id: UUID, service_id: UUID) -> None:
        svc = db.query(Service).filter(Service.id == service_id, Service.tenant_id == tenant_id).first()
        if not svc:
            raise NotFoundError("Serviço não encontrado neste tenant.")

    def _build_response_dict(self, photo: ProcedurePhoto, mf: Optional[MediaFile] = None) -> dict:
        """Merge media_file fields into the photo for serialization."""
        photo.file_url = mf.file_url if mf else None
        photo.file_type = mf.file_type if mf else None
        photo.mime_type = mf.mime_type if mf else None
        photo.original_filename = mf.original_filename if mf else None
        return photo

    # ---- Administrative ----

    def list_photos_for_procedure(
        self,
        db: Session,
        tenant_id: UUID,
        procedure_id: UUID,
    ) -> List[ProcedurePhoto]:
        self._get_procedure(db, tenant_id, procedure_id)
        photos = (
            db.query(ProcedurePhoto)
            .filter(
                ProcedurePhoto.tenant_id == tenant_id,
                ProcedurePhoto.procedure_history_id == procedure_id,
            )
            .order_by(ProcedurePhoto.created_at.asc())
            .all()
        )
        for photo in photos:
            mf = db.query(MediaFile).filter(MediaFile.id == photo.media_file_id).first()
            self._build_response_dict(photo, mf)
        return photos

    def get_photo(self, db: Session, tenant_id: UUID, procedure_id: UUID, photo_id: UUID) -> ProcedurePhoto:
        self._get_procedure(db, tenant_id, procedure_id)
        photo = (
            db.query(ProcedurePhoto)
            .filter(
                ProcedurePhoto.id == photo_id,
                ProcedurePhoto.tenant_id == tenant_id,
                ProcedurePhoto.procedure_history_id == procedure_id,
            )
            .first()
        )
        if not photo:
            raise NotFoundError("Foto de procedimento não encontrada.")
        mf = db.query(MediaFile).filter(MediaFile.id == photo.media_file_id).first()
        return self._build_response_dict(photo, mf)

    def add_photo(
        self,
        db: Session,
        tenant_id: UUID,
        procedure_id: UUID,
        data: dict,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ProcedurePhoto:
        ph = self._get_procedure(db, tenant_id, procedure_id)
        mf = self._get_media_file(db, tenant_id, data["media_file_id"])

        if data.get("service_id"):
            self._validate_service(db, tenant_id, data["service_id"])

        photo = ProcedurePhoto(
            tenant_id=tenant_id,
            procedure_history_id=procedure_id,
            customer_account_id=ph.customer_account_id,
            tenant_customer_id=ph.tenant_customer_id,
            media_file_id=data["media_file_id"],
            service_id=data.get("service_id"),
            photo_type=data["photo_type"],
            visibility=data.get("visibility", PhotoVisibility.internal),
            caption=data.get("caption"),
        )
        db.add(photo)
        db.flush()

        audit_service.log(
            db=db,
            action="procedure_photo_added",
            entity_type="procedure_photo",
            entity_id=photo.id,
            tenant_id=tenant_id,
            user_id=user_id,
            new_values={
                "photo_type": photo.photo_type.value,
                "visibility": photo.visibility.value,
                "procedure_history_id": str(procedure_id),
                "media_file_id": str(photo.media_file_id),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if photo.visibility == PhotoVisibility.customer_visible:
            customer_event_service.emit(
                db=db,
                event_type="procedure_photo_added",
                tenant_id=tenant_id,
                customer_account_id=ph.customer_account_id,
                tenant_customer_id=ph.tenant_customer_id,
                entity_type="procedure_photo",
                entity_id=photo.id,
                metadata={
                    "photo_type": photo.photo_type.value,
                    "procedure_history_id": str(procedure_id),
                    "media_file_id": str(photo.media_file_id),
                    "service_id": str(photo.service_id) if photo.service_id else None,
                },
            )

        db.commit()
        db.refresh(photo)
        return self._build_response_dict(photo, mf)

    def update_photo(
        self,
        db: Session,
        tenant_id: UUID,
        procedure_id: UUID,
        photo_id: UUID,
        data: dict,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ProcedurePhoto:
        photo = self.get_photo(db, tenant_id, procedure_id, photo_id)
        old_values = {
            "photo_type": photo.photo_type.value,
            "visibility": photo.visibility.value,
            "caption": photo.caption,
            "service_id": str(photo.service_id) if photo.service_id else None,
        }

        if data.get("service_id"):
            self._validate_service(db, tenant_id, data["service_id"])

        for field, value in data.items():
            if value is not None:
                setattr(photo, field, value)

        db.flush()
        audit_service.log(
            db=db,
            action="procedure_photo_updated",
            entity_type="procedure_photo",
            entity_id=photo.id,
            tenant_id=tenant_id,
            user_id=user_id,
            old_values=old_values,
            new_values={
                "photo_type": photo.photo_type.value,
                "visibility": photo.visibility.value,
                "caption": photo.caption,
                "service_id": str(photo.service_id) if photo.service_id else None,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.commit()
        db.refresh(photo)
        mf = db.query(MediaFile).filter(MediaFile.id == photo.media_file_id).first()
        return self._build_response_dict(photo, mf)

    def remove_photo(
        self,
        db: Session,
        tenant_id: UUID,
        procedure_id: UUID,
        photo_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        photo = self.get_photo(db, tenant_id, procedure_id, photo_id)
        audit_service.log(
            db=db,
            action="procedure_photo_removed",
            entity_type="procedure_photo",
            entity_id=photo.id,
            tenant_id=tenant_id,
            user_id=user_id,
            old_values={
                "photo_type": photo.photo_type.value,
                "visibility": photo.visibility.value,
                "media_file_id": str(photo.media_file_id),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        # Remove only the link — media_file is preserved
        db.query(ProcedurePhoto).filter(ProcedurePhoto.id == photo_id).delete()
        db.commit()

    # ---- Customer portal ----

    def list_customer_visible_photos(
        self,
        db: Session,
        tenant_id: UUID,
        procedure_id: UUID,
        customer_account_id: UUID,
    ) -> List[ProcedurePhoto]:
        ph = (
            db.query(ProcedureHistory)
            .filter(
                ProcedureHistory.id == procedure_id,
                ProcedureHistory.tenant_id == tenant_id,
                ProcedureHistory.customer_account_id == customer_account_id,
            )
            .first()
        )
        if not ph:
            raise NotFoundError("Histórico de procedimento não encontrado.")

        photos = (
            db.query(ProcedurePhoto)
            .filter(
                ProcedurePhoto.tenant_id == tenant_id,
                ProcedurePhoto.procedure_history_id == procedure_id,
                ProcedurePhoto.customer_account_id == customer_account_id,
                ProcedurePhoto.visibility == PhotoVisibility.customer_visible,
            )
            .order_by(ProcedurePhoto.created_at.asc())
            .all()
        )
        for photo in photos:
            mf = db.query(MediaFile).filter(MediaFile.id == photo.media_file_id).first()
            self._build_response_dict(photo, mf)
        return photos


procedure_photo_service = ProcedurePhotoService()
