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


def _save_local(content: bytes, rel_path: str) -> str:
    abs_path = os.path.join(os.getcwd(), rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as f:
        f.write(content)
    return f"/{rel_path}"


def _save_r2(content: bytes, key: str, content_type: str) -> str:
    import boto3
    endpoint = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )
    s3.put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=key,
        Body=content,
        ContentType=content_type,
    )
    base = settings.R2_PUBLIC_URL.rstrip("/")
    return f"{base}/{key}"


def save_file(content: bytes, tenant_id, file_type: str, ext: str, content_type: str) -> str:
    unique_name = f"{uuid.uuid4().hex}{ext}"
    key = f"uploads/{tenant_id}/{file_type}/{unique_name}"
    if settings.UPLOAD_STORAGE == "r2":
        return _save_r2(content, key, content_type)
    return _save_local(content, key)


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
    """Faz upload de um arquivo de mídia (local ou Cloudflare R2)."""

    if file.content_type not in ALLOWED_MIME:
        raise ValidationError(
            f"Tipo de arquivo não permitido: {file.content_type}. "
            f"Permitidos: {', '.join(ALLOWED_MIME)}"
        )

    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise ValidationError(
            f"Arquivo muito grande. Máximo permitido: {settings.MAX_UPLOAD_SIZE_MB}MB."
        )

    ext = os.path.splitext(file.filename or "file")[1].lower() or ".jpg"
    file_url = save_file(content, tenant.id, file_type, ext, file.content_type)

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

    if settings.UPLOAD_STORAGE == "r2":
        try:
            import boto3
            endpoint = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
            s3 = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                region_name="auto",
            )
            base = settings.R2_PUBLIC_URL.rstrip("/")
            key = media.file_url.replace(base + "/", "")
            s3.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
        except Exception:
            pass
    else:
        try:
            local_path = os.path.join(os.getcwd(), media.file_url.lstrip("/"))
            if os.path.exists(local_path):
                os.remove(local_path)
        except Exception:
            pass

    db.delete(media)
    db.commit()
    return {"message": "Arquivo removido."}
