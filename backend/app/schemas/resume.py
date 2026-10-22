"""简历相关 Schema。"""
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


ResumeTemplate = Literal["default", "technical", "management", "compact"]


class ResumePreferences(BaseModel):
    target_level: str | None = Field(None, description="目标级别：junior/mid/senior")
    highlight_direction: list[str] = Field([], description="希望突出的方向，如：技术深度/项目经验")
    page_limit: int = Field(1, ge=1, le=5, description="页数限制")
    language: Literal["zh", "en"] = "zh"
    template: ResumeTemplate = Field(
        "default", description="渲染模板：default/technical/management/compact",
    )


class ResumeGenerateRequest(BaseModel):
    jd_id: uuid.UUID
    preferences: ResumePreferences = ResumePreferences()


class ResumeGenerateResponse(BaseModel):
    id: uuid.UUID
    version_name: str
    match_score: int | None
    highlights: list[Any]
    gaps: list[Any]
    suggestions: list[Any]
    resume_data: dict[str, Any]
    status: str
    error_message: str | None = None


class ResumeResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    jd_id: uuid.UUID | None
    version_name: str
    resume_data: dict[str, Any]
    match_score: int | None
    highlights: list[Any]
    gaps: list[Any]
    suggestions: list[Any]
    html_template: str
    preferences: dict[str, Any] = Field(default_factory=dict)
    pdf_path: str | None
    status: str
    error_message: str | None = None
    # AI 候选补强项目。存量行是 NULL，前端据此隐藏补强面板
    enhancements: list[Any] = Field(default_factory=list)
    has_interview_prep: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("preferences", mode="before")
    @classmethod
    def _null_to_empty_dict(cls, v: Any) -> Any:
        return v if isinstance(v, dict) else {}

    @field_validator("enhancements", mode="before")
    @classmethod
    def _null_to_empty_list(cls, v: Any) -> Any:
        """存量行的 enhancements 是 NULL，必须归一化成 []。

        坑：`default_factory=list` 只在字段**缺失**时生效。from_attributes 下
        属性存在但值为 None 时它不管，pydantic 直接报 list_type 错误 →
        简历列表接口 500，整页简历都打不开（不只是新功能用不了）。
        """
        return v if isinstance(v, list) else []


class ResumeExportRequest(BaseModel):
    format: Literal["pdf"] = "pdf"
    template: ResumeTemplate | None = Field(None, description="可覆盖简历默认模板")


class ResumeDataUpdateRequest(BaseModel):
    """编辑器保存：整份 resume_data 提交，服务端做结构校验后覆盖。

    match_details 由服务端从库里原样保留 —— 匹配证据不允许前端改写。
    """
    resume_data: dict[str, Any]


class ResumeVersionMeta(BaseModel):
    id: uuid.UUID
    version_no: int
    label: str
    match_score: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ResumeVersionDetail(ResumeVersionMeta):
    resume_data: dict[str, Any]


class EnhancementPlacement(BaseModel):
    index: int = Field(..., ge=0, le=7)
    target_source_ref: str = Field(..., pattern=r"^work_experiences\[\d+\]$")
    # 勾选后把确认的 bullets 同步追加到档案 WorkExperience.achievements，
    # 以后生成其他简历时系统就知道用户有这段经历，不必每份简历重复确认
    write_back_profile: bool = False


class EnhancementApplyRequest(BaseModel):
    """用户确认后，将建议 bullet 融入指定的已有工作经历。"""
    placements: list[EnhancementPlacement] = Field(..., min_length=1)
    confirmed: Literal[True] = Field(
        ..., description="用户确认这些职责/技术确实发生在所选公司经历中",
    )


class ResumeDiagnosisRequest(BaseModel):
    resume_text: str = Field(..., min_length=10, description="从 PDF/Word 提取的简历纯文本")
    keywords_hint: list[str] = Field([], description="可选：希望重点检查的关键词")


class InterviewQARequest(BaseModel):
    question_count: int = Field(8, ge=3, le=20)


class InterviewPrepareRequest(BaseModel):
    question_count: int = Field(10, ge=3, le=20, description="题库题目数量")


class InterviewPrepResponse(BaseModel):
    id: uuid.UUID
    resume_id: uuid.UUID
    research: dict[str, Any]
    outline: dict[str, Any]
    questions: list[Any]
    status: str = "generated"                 # pending / generated / failed
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
