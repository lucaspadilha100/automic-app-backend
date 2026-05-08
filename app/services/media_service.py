from pathlib import Path
from typing import Optional
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ValidationError, NotFoundError
from app.models.media import MediaFile


class MediaService:
    """Local storage abstraction prepared for future S3/R2 providers."""

    PUBLIC_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    BLOCKED_EXTENSIONS = {".exe", ".bat", ".cmd", ".sh", ".php", ".js", ".jar", ".msi"}

    def validate_upload(self, file: UploadFile, size_bytes: Optional[int] = None) -> None:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix in self.BLOCKED_EXTENSIONS:
            raise ValidationError("Tipo de arquivo não permitido.")
        if file.content_type not in self.PUBLIC_IMAGE_MIME_TYPES:
            raise ValidationError("MIME type não permitido para este upload.")
        if size_bytes is not None and size_bytes > settings.max_upload_size_bytes:
            raise ValidationError("Arquivo excede o tamanho máximo permitido.")

    def tenant_upload_dir(self, tenant_id) -> Path:
        path = Path(settings.UPLOAD_DIR) / str(tenant_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_for_tenant(self, db: Session, tenant_id, media_id) -> MediaFile:
        media = db.query(MediaFile).filter(MediaFile.id == media_id, MediaFile.tenant_id == tenant_id).first()
        if not media:
            raise NotFoundError("MEDIA_NOT_FOUND", "Arquivo não encontrado.")
        return media

    def create_record(
        self,
        db: Session,
        tenant_id,
        file_url: str,
        file_type: str,
        original_filename: str,
        mime_type: str,
        size_bytes: int,
        uploaded_by_user_id=None,
        entity_type: Optional[str] = None,
        entity_id=None,
    ) -> MediaFile:
        media = MediaFile(
            tenant_id=tenant_id,
            uploaded_by_user_id=uploaded_by_user_id,
            file_url=file_url,
            file_type=file_type,
            original_filename=original_filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        db.add(media)
        db.flush()
        return media


media_service = MediaService()
