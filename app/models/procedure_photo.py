import enum
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class PhotoType(str, enum.Enum):
    before = "before"
    after = "after"
    progress = "progress"


class PhotoVisibility(str, enum.Enum):
    internal = "internal"
    customer_visible = "customer_visible"
    public = "public"


class ProcedurePhoto(Base, UUIDPrimaryKey, TimestampMixin):
    """Photo (before/after/progress) linked to a procedure history record."""
    __tablename__ = "procedure_photos"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    procedure_history_id = Column(UUID(as_uuid=True), ForeignKey("procedure_history.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_account_id = Column(UUID(as_uuid=True), ForeignKey("customer_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    tenant_customer_id = Column(UUID(as_uuid=True), ForeignKey("tenant_customers.id", ondelete="SET NULL"), nullable=True, index=True)
    media_file_id = Column(UUID(as_uuid=True), ForeignKey("media_files.id", ondelete="RESTRICT"), nullable=False, index=True)
    service_id = Column(UUID(as_uuid=True), ForeignKey("services.id", ondelete="SET NULL"), nullable=True)

    photo_type = Column(
        SAEnum(PhotoType, name="photo_type_enum", create_type=False),
        nullable=False,
        index=True,
    )
    visibility = Column(
        SAEnum(PhotoVisibility, name="photo_visibility_enum", create_type=False),
        nullable=False,
        default=PhotoVisibility.internal,
        index=True,
    )
    caption = Column(Text, nullable=True)

    procedure_history = relationship("ProcedureHistory", back_populates="photos")
    media_file = relationship("MediaFile")
