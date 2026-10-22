"""技能 Schema。"""
import uuid
from typing import Any

from pydantic import BaseModel, Field


class SkillCreate(BaseModel):
    name: str = Field(..., max_length=50)
    category: str | None = None
    proficiency: int | None = Field(None, ge=1, le=5)   # 熟练度 1-5
    order_index: int = 0
    visibility: bool = True
    custom_fields: dict[str, Any] = {}


class SkillUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    proficiency: int | None = Field(None, ge=1, le=5)
    order_index: int | None = None
    visibility: bool | None = None
    custom_fields: dict[str, Any] | None = None


class SkillResponse(SkillCreate):
    id: uuid.UUID
    profile_id: uuid.UUID

    model_config = {"from_attributes": True}
