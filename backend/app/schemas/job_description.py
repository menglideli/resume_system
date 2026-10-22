"""JD 解析相关 Schema。"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JDParseRequest(BaseModel):
    raw_text: str = Field(..., min_length=10, description="岗位描述全文")
    company_name: str | None = None
    position_title: str | None = None


class JDParsedData(BaseModel):
    """JD 结构化解析结果（字段均可选，AI 尽力填充）。"""
    company: str | None = None
    position: str | None = None
    hard_requirements: list[str] = []
    soft_requirements: list[str] = []
    core_responsibilities: list[str] = []
    bonus_items: list[str] = []
    keywords: list[str] = []
    ats_keywords: list[str] = []
    education_requirement: str | None = None
    experience_years: str | None = None
    salary_range: str | None = None


class MatchPreview(BaseModel):
    profile_completeness: int = 0
    estimated_match: int = 0


class JDParseResponse(BaseModel):
    id: uuid.UUID
    parsed_data: dict[str, Any]
    match_preview: MatchPreview


class JDResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    company_name: str | None
    position_title: str | None
    raw_text: str
    parsed_data: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}
