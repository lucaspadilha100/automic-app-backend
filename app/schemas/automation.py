from pydantic import BaseModel, ConfigDict, field_validator
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid

from app.models.automation import ActionType


class AutomationRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_event: str
    conditions: Optional[Dict[str, Any]] = None
    action_type: ActionType
    action_config: Dict[str, Any] = {}
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name não pode estar vazio.")
        return v

    @field_validator("trigger_event")
    @classmethod
    def trigger_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("trigger_event não pode estar vazio.")
        return v


class AutomationRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_event: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    action_type: Optional[ActionType] = None
    action_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class AutomationRuleStatusUpdate(BaseModel):
    is_active: bool


class AutomationRuleResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: Optional[str]
    trigger_event: str
    conditions: Optional[Dict[str, Any]]
    action_type: ActionType
    action_config: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
