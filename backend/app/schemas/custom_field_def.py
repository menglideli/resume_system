"""自定义字段定义 Schema：档案各版块可由用户自行追加字段。"""
import uuid
from typing import Literal

from pydantic import BaseModel, Field

# 与档案子资源路由 key 一致的版块标识
SECTIONS = (
    "basic", "educations", "work-experiences", "projects",
    "skills", "certifications", "family-members",
)


class FieldDefCreate(BaseModel):
    section: str = Field(..., max_length=30)
    name: str = Field(..., min_length=1, max_length=50)
    label: str = Field(..., min_length=1, max_length=50)
    type: Literal["text", "number", "date", "textarea"] = "text"


class FieldDefUpdate(BaseModel):
    """字段名（存储 key）不可改，仅调整显示名与类型。"""
    label: str | None = Field(None, min_length=1, max_length=50)
    type: Literal["text", "number", "date", "textarea"] | None = None


class FieldDefResponse(FieldDefCreate):
    id: uuid.UUID
    profile_id: uuid.UUID
    order_index: int

    model_config = {"from_attributes": True}
