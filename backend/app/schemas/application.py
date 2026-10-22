"""投递管理 Schema。"""
import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Channel = Literal["email", "website", "official"]
AppStatus = Literal["applied", "viewed", "interview", "offer", "rejected"]


class ApplicationCreate(BaseModel):
    resume_id: uuid.UUID | None = None
    jd_id: uuid.UUID | None = None
    company_name: str = Field(..., max_length=100)
    position_title: str = Field(..., max_length=100)
    channel: Channel = "website"
    notes: str | None = None
    follow_up_date: date | None = None


class ApplicationUpdate(BaseModel):
    status: AppStatus | None = None
    notes: str | None = None
    follow_up_date: date | None = None
    channel: Channel | None = None


class ApplicationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    resume_id: uuid.UUID | None
    jd_id: uuid.UUID | None
    company_name: str
    position_title: str
    channel: str
    status: str
    applied_at: datetime
    notes: str | None
    follow_up_date: date | None
    # 关联摘要（列表接口附带）
    resume_version_name: str | None = None
    jd_company: str | None = None
    jd_position: str | None = None
    # 投递版本锁定摘要：大字段（resume_snapshot/jd_snapshot）不在列表返回，走 /snapshot 接口
    has_snapshot: bool = False
    snapshot_template: str | None = None
    snapshot_match_score: int | None = None
    has_snapshot_pdf: bool = False

    model_config = {"from_attributes": True}


class ApplicationSnapshotResponse(BaseModel):
    """投递快照详情：招聘方当时实际看到的简历与 JD。"""
    id: uuid.UUID
    company_name: str
    position_title: str
    channel: str
    status: str
    applied_at: datetime
    resume_version_name: str | None = None
    snapshot_template: str | None = None
    snapshot_match_score: int | None = None
    has_snapshot_pdf: bool = False
    resume_snapshot: dict[str, Any] | None = None
    jd_snapshot: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class TrendPoint(BaseModel):
    date: str                       # YYYY-MM-DD
    count: int


class ApplicationStats(BaseModel):
    total: int
    by_status: dict[str, int]
    by_channel: dict[str, int]
    conversion_rate: float          # (interview + offer) / total * 100
    recent_7_days: int
    trend_30d: list[TrendPoint] = []  # 近 30 天每日投递量（零填充）


class ApplicationListResponse(BaseModel):
    total: int
    items: list[ApplicationResponse]
