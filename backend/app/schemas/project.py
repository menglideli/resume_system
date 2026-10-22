"""项目经历 Schema。"""
import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., max_length=100)
    role: str | None = None
    tech_stack: list[str] = []
    start_date: date | None = None
    end_date: date | None = None
    description: list[str] = []
    highlights: list[str] = []
    url: str | None = None
    order_index: int = 0
    visibility: bool = True
    priority: int = 0
    custom_fields: dict[str, Any] = {}


class ProjectUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    tech_stack: list[str] | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: list[str] | None = None
    highlights: list[str] | None = None
    url: str | None = None
    order_index: int | None = None
    visibility: bool | None = None
    priority: int | None = None
    custom_fields: dict[str, Any] | None = None


class ProjectResponse(ProjectCreate):
    id: uuid.UUID
    profile_id: uuid.UUID

    model_config = {"from_attributes": True}
