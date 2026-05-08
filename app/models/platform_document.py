"""
PlatformDocument — versioned legal/marketing copy for the AUTOMIC platform itself.

Each document is identified by a `document_type` (singleton-per-type via
unique constraint). When the master updates a document, a new version
counter is bumped. Only the *current* row per type is exposed publicly,
so this is effectively a single source of truth per kind.

This is *separate* from `TenantTerm` (the tenant's own terms shown to
its end customers).
"""
import enum
from sqlalchemy import Column, String, Text, Integer, Enum as SAEnum, UniqueConstraint
from app.models.base_model import UUIDPrimaryKey, TimestampMixin
from db.base import Base


class PlatformDocumentType(str, enum.Enum):
    terms_of_service = "terms_of_service"
    privacy_policy = "privacy_policy"
    data_processing_agreement = "data_processing_agreement"
    acceptable_use_policy = "acceptable_use_policy"


class PlatformDocument(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "platform_documents"
    __table_args__ = (
        UniqueConstraint("document_type", name="uq_platform_documents_type"),
    )

    document_type = Column(
        SAEnum(PlatformDocumentType, name="platform_document_type", create_type=False),
        nullable=False, index=True,
    )
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    version = Column(String(20), nullable=False, default="1.0")
    revision_count = Column(Integer, nullable=False, default=1)
