"""工作经历 Schema。"""
import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class WorkCreate(BaseModel):
    company: str = Field(..., max_length=100)
    position: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: list[str] = []        # bullet points
    achievements: list[str] = []       # 量化成果
    is_current: bool = False
    order_index: int = 0
    visibility: bool = True
    priority: int = 0
    custom_fields: dict[str, Any] = {}


class WorkUpdate(BaseModel):
    company: str | None = None
    position: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: list[str] | None = None
    achievements: list[str] | None = None
    is_current: bool | None = None
    order_index: int | None = None
    visibility: bool | None = None
    priority: int | None = None
    custom_fields: dict[str, Any] | None = None


class WorkResponse(WorkCreate):
    id: uuid.UUID
    profile_id: uuid.UUID

    model_config = {"from_attributes": True}
