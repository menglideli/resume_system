"""自定义信息块 Schema：块定义 + 条目记录。"""
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class BlockFieldDef(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    label: str | None = Field(None, max_length=50)
    type: Literal["text", "number", "date", "textarea"] = "text"


class BlockCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    fields: list[BlockFieldDef] = Field(..., min_length=1)

    @field_validator("fields")
    @classmethod
    def _check_fields(cls, v: list[BlockFieldDef]) -> list[BlockFieldDef]:
        names = [f.name for f in v]
        if len(names) != len(set(names)):
            raise ValueError("字段名不能重复")
        return v


class BlockUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=50)
    fields: list[BlockFieldDef] | None = Field(None, min_length=1)


class BlockEntryCreate(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class BlockEntryResponse(BaseModel):
    id: uuid.UUID
    block_id: uuid.UUID
    data: dict[str, Any]
    order_index: int

    model_config = {"from_attributes": True}


class BlockResponse(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    name: str
    fields: list[dict[str, Any]]
    order_index: int
    entries: list[BlockEntryResponse] = []

    model_config = {"from_attributes": True}
