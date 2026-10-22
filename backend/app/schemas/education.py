"""教育经历 Schema。"""
import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class EducationCreate(BaseModel):
    school: str = Field(..., max_length=100)
    major: str | None = None
    degree: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    gpa: str | None = None
    courses: list[str] = []
    is_current: bool = False
    order_index: int = 0
    visibility: bool = True
    priority: int = 0
    custom_fields: dict[str, Any] = {}


class EducationUpdate(BaseModel):
    school: str | None = None
    major: str | None = None
    degree: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    gpa: str | None = None
    courses: list[str] | None = None
    is_current: bool | None = None
    order_index: int | None = None
    visibility: bool | None = None
    priority: int | None = None
    custom_fields: dict[str, Any] | None = None


class EducationResponse(EducationCreate):
    id: uuid.UUID
    profile_id: uuid.UUID

    model_config = {"from_attributes": True}
