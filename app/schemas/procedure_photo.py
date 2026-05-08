from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
import uuid

from app.models.procedure_photo import PhotoType, PhotoVisibility


class ProcedurePhotoCreate(BaseModel):
    media_file_id: uuid.UUID
    photo_type: PhotoType
    visibility: PhotoVisibility = PhotoVisibility.internal
    caption: Optional[str] = None
    service_id: Optional[uuid.UUID] = None


class ProcedurePhotoUpdate(BaseModel):
    photo_type: Optional[PhotoType] = None
    visibility: Optional[PhotoVisibility] = None
    caption: Optional[str] = None
    service_id: Optional[uuid.UUID] = None


class ProcedurePhotoResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    procedure_history_id: uuid.UUID
    customer_account_id: Optional[uuid.UUID]
    tenant_customer_id: Optional[uuid.UUID]
    media_file_id: uuid.UUID
    service_id: Optional[uuid.UUID]
    photo_type: PhotoType
    visibility: PhotoVisibility
    caption: Optional[str]
    # Denormalized media_file fields for convenience
    file_url: Optional[str] = None
    file_type: Optional[str] = None
    mime_type: Optional[str] = None
    original_filename: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProcedurePhotoCustomerResponse(BaseModel):
    """Subset of fields safe for the customer portal — no internal details."""
    id: uuid.UUID
    procedure_history_id: uuid.UUID
    media_file_id: uuid.UUID
    service_id: Optional[uuid.UUID]
    photo_type: PhotoType
    caption: Optional[str]
    file_url: Optional[str] = None
    file_type: Optional[str] = None
    mime_type: Optional[str] = None
    original_filename: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
