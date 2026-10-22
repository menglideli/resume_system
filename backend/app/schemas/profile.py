"""用户档案 Schema（含聚合完整档案）。"""
import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.certification import CertificationResponse
from app.schemas.custom_field_def import FieldDefResponse
from app.schemas.education import EducationResponse
from app.schemas.family import FamilyResponse
from app.schemas.profile_block import BlockResponse
from app.schemas.project import ProjectResponse
from app.schemas.skill import SkillResponse
from app.schemas.work import WorkResponse


class ProfileUpdate(BaseModel):
    name: str | None = Field(None, max_length=50)
    gender: str | None = None
    birth_date: date | None = None
    phone: str | None = None
    email: str | None = None
    location: str | None = None
    political_status: str | None = None
    avatar_url: str | None = None
    summary: str | None = None
    custom_fields: dict[str, Any] | None = None


class ProfileResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    gender: str | None
    birth_date: date | None
    phone: str | None
    email: str | None
    location: str | None
    political_status: str | None
    avatar_url: str | None
    summary: str | None
    custom_fields: dict[str, Any] = {}
    completeness_score: int

    model_config = {"from_attributes": True}


class ProfileFullResponse(ProfileResponse):
    """完整档案：基础信息 + 六类子记录 + 自定义信息块 + 自定义字段定义。"""
    educations: list[EducationResponse] = []
    work_experiences: list[WorkResponse] = []
    projects: list[ProjectResponse] = []
    skills: list[SkillResponse] = []
    certifications: list[CertificationResponse] = []
    family_members: list[FamilyResponse] = []
    custom_blocks: list[BlockResponse] = []
    field_defs: list[FieldDefResponse] = []
