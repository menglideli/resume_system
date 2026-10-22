"""家庭成员 Schema（报名表用）。"""
import uuid
from typing import Any

from pydantic import BaseModel, Field


class FamilyCreate(BaseModel):
    name: str = Field(..., max_length=50)
    relationship: str | None = None
    work_unit: str | None = None
    position: str | None = None
    phone: str | None = None
    custom_fields: dict[str, Any] = {}


class FamilyUpdate(BaseModel):
    name: str | None = None
    relationship: str | None = None
    work_unit: str | None = None
    position: str | None = None
    phone: str | None = None
    custom_fields: dict[str, Any] | None = None


class FamilyResponse(FamilyCreate):
    id: uuid.UUID
    profile_id: uuid.UUID

    model_config = {"from_attributes": True}
