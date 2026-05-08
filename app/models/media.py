from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from db.base import Base
from app.models.base_model import UUIDPrimaryKey


class MediaFile(Base, UUIDPrimaryKey):
    __tablename__ = "media_files"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    uploaded_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    file_url = Column(String(1000), nullable=False)
    file_type = Column(String(50), nullable=True)
    # logo | favicon | cover | service_image | professional_photo | before_after | other
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    original_filename = Column(String(300), nullable=True)
    mime_type = Column(String(100), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
