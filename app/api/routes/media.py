import os
import uuid
import shutil
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session

from db.session import get_db
from app.core.config import settings
from app.core.dependencies import require_active_tenant, require_manager_or_above
from app.core.exceptions import ValidationError
from app.models.user import User
from app.models.tenant import Tenant
from app.models.media import MediaFile

router = APIRouter(prefix="/media", tags=["Mídia & Uploads"])

ALLOWED_MIME = {
    "image/jpeg", "image/png", "image/webp", "image/gif", "image/svg+xml"
}

FILE_TYPE_MAP = {
    "logo": "logo",
    "favicon": "favicon",
    "cover": "cover",
    "service_image": "service_image",
    "professional_photo": "professional_photo",
    "before_after": "before_after",
}


def _save_local(file: UploadFile, dest_path: str) -> str:
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return dest_path


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    file_type: str = "other",
    entity_type: Optional[str] = None,
    entity_id: Optional[uuid.UUID] = None,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    """Faz upload de um arquivo de mídia (local ou cloud conforme configuração)."""

    # Validate MIME type
    if file.content_type not in ALLOWED_MIME:
        raise ValidationError(
            f"Tipo de arquivo não permitido: {file.content_type}. "
            f"Permitidos: {', '.join(ALLOWED_MIME)}"
        )

    # Validate size
    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise ValidationError(
            f"Arquivo muito grande. Máximo permitido: {settings.MAX_UPLOAD_SIZE_MB}MB."
        )
    await file.seek(0)

    # Build unique filename
    ext = os.path.splitext(file.filename or "file")[1].lower() or ".jpg"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    rel_path = f"uploads/{tenant.id}/{file_type}/{unique_name}"
    abs_path = os.path.join(os.getcwd(), rel_path)

    # Save to local storage (extend here for S3/R2)
    _save_local(file, abs_path)

    # Serve URL (in prod, replace with CDN URL)
    file_url = f"/{rel_path}"

    media = MediaFile(
        tenant_id=tenant.id,
        uploaded_by_user_id=current_user.id,
        file_url=file_url,
        file_type=file_type,
        entity_type=entity_type,
        entity_id=entity_id,
        original_filename=file.filename,
        mime_type=file.content_type,
        size_bytes=len(content),
        created_at=datetime.now(timezone.utc),
    )
    db.add(media)
    db.commit()
    db.refresh(media)

    return {
        "id": str(media.id),
        "file_url": media.file_url,
        "file_type": media.file_type,
        "original_filename": media.original_filename,
        "size_bytes": media.size_bytes,
        "created_at": media.created_at.isoformat(),
    }


@router.get("")
def list_media(
    file_type: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[uuid.UUID] = None,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    q = db.query(MediaFile).filter(MediaFile.tenant_id == tenant.id)
    if file_type:
        q = q.filter(MediaFile.file_type == file_type)
    if entity_type:
        q = q.filter(MediaFile.entity_type == entity_type)
    if entity_id:
        q = q.filter(MediaFile.entity_id == entity_id)
    return q.order_by(MediaFile.created_at.desc()).all()


@router.delete("/{media_id}")
def delete_media(
    media_id: uuid.UUID,
    tenant: Tenant = Depends(require_active_tenant),
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
):
    from app.core.exceptions import NotFoundError
    media = db.query(MediaFile).filter(
        MediaFile.id == media_id, MediaFile.tenant_id == tenant.id
    ).first()
    if not media:
        raise NotFoundError("MEDIA_NOT_FOUND", "Arquivo não encontrado.")

    # Try to remove local file
    try:
        local_path = os.path.join(os.getcwd(), media.file_url.lstrip("/"))
        if os.path.exists(local_path):
            os.remove(local_path)
    except Exception:
        pass

    db.delete(media)
    db.commit()
    return {"message": "Arquivo removido."}
