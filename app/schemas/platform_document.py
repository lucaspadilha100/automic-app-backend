from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime
import uuid

from app.models.platform_document import PlatformDocumentType


class PlatformDocumentResponse(BaseModel):
    id: uuid.UUID
    document_type: PlatformDocumentType
    title: str
    content: str
    version: str
    revision_count: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PlatformDocumentUpsert(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    version: str = Field("1.0", min_length=1, max_length=20)
