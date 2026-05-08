from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid

from app.models.custom_form import FormType, FieldType


# ── Form schemas ──────────────────────────────────────────────────────────────

class CustomFormCreate(BaseModel):
    title: str
    description: Optional[str] = None
    form_type: FormType
    is_active: bool = True


class CustomFormUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    form_type: Optional[FormType] = None
    is_active: Optional[bool] = None


class CustomFormStatusUpdate(BaseModel):
    is_active: bool


class CustomFormFieldResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    form_id: uuid.UUID
    label: str
    field_type: FieldType
    required: bool
    options: Optional[List[str]]
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomFormResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    description: Optional[str]
    form_type: FormType
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomFormWithFieldsResponse(CustomFormResponse):
    fields: List[CustomFormFieldResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ── Field schemas ─────────────────────────────────────────────────────────────

class CustomFormFieldCreate(BaseModel):
    label: str
    field_type: FieldType
    required: bool = False
    options: Optional[List[str]] = None
    sort_order: int = 0

    @model_validator(mode="after")
    def options_required_for_select(self) -> "CustomFormFieldCreate":
        if self.field_type in (FieldType.select, FieldType.multiselect):
            if not self.options:
                raise ValueError("options é obrigatório para campos select e multiselect.")
        return self


class CustomFormFieldUpdate(BaseModel):
    label: Optional[str] = None
    field_type: Optional[FieldType] = None
    required: Optional[bool] = None
    options: Optional[List[str]] = None
    sort_order: Optional[int] = None


# ── Response/submission schemas ───────────────────────────────────────────────

class CustomFormSubmit(BaseModel):
    answers: Dict[str, Any]  # field_id (str) -> answer value
    appointment_id: Optional[uuid.UUID] = None


class CustomFormResponseResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    form_id: uuid.UUID
    customer_account_id: Optional[uuid.UUID]
    tenant_customer_id: Optional[uuid.UUID]
    appointment_id: Optional[uuid.UUID]
    answers: Dict[str, Any]
    submitted_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
