import enum
from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from db.base import Base
from app.models.base_model import TimestampMixin, UUIDPrimaryKey


class FormType(str, enum.Enum):
    anamnesis = "anamnesis"
    pre_service = "pre_service"
    post_service = "post_service"
    evaluation = "evaluation"


class FieldType(str, enum.Enum):
    text = "text"
    textarea = "textarea"
    number = "number"
    date = "date"
    boolean = "boolean"
    select = "select"
    multiselect = "multiselect"


class CustomForm(Base, UUIDPrimaryKey, TimestampMixin):
    """Tenant-specific custom form (anamnesis, pre/post service, evaluation)."""
    __tablename__ = "custom_forms"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    form_type = Column(
        SAEnum(FormType, name="form_type_enum", create_type=False),
        nullable=False,
        index=True,
    )
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    fields = relationship(
        "CustomFormField",
        back_populates="form",
        cascade="all, delete-orphan",
        order_by="CustomFormField.sort_order",
    )
    responses = relationship("CustomFormResponse", back_populates="form", cascade="all, delete-orphan")


class CustomFormField(Base, UUIDPrimaryKey, TimestampMixin):
    """A single field within a custom form."""
    __tablename__ = "custom_form_fields"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    form_id = Column(UUID(as_uuid=True), ForeignKey("custom_forms.id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(String(255), nullable=False)
    field_type = Column(
        SAEnum(FieldType, name="field_type_enum", create_type=False),
        nullable=False,
    )
    required = Column(Boolean, nullable=False, default=False)
    options = Column(JSONB, nullable=True)  # list of strings for select/multiselect
    sort_order = Column(Integer, nullable=False, default=0)

    form = relationship("CustomForm", back_populates="fields")


class CustomFormResponse(Base, UUIDPrimaryKey, TimestampMixin):
    """A customer's submitted answers for a custom form."""
    __tablename__ = "custom_form_responses"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    form_id = Column(UUID(as_uuid=True), ForeignKey("custom_forms.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_account_id = Column(UUID(as_uuid=True), ForeignKey("customer_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    tenant_customer_id = Column(UUID(as_uuid=True), ForeignKey("tenant_customers.id", ondelete="SET NULL"), nullable=True, index=True)
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True)
    answers = Column(JSONB, nullable=False, default=dict)
    submitted_at = Column(DateTime(timezone=True), nullable=False)

    form = relationship("CustomForm", back_populates="responses")
