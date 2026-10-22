"""简历版本表 ORM 模型。"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    jd_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("job_descriptions.id", ondelete="SET NULL"), index=True)
    version_name: Mapped[str] = mapped_column(String(200), nullable=False)
    resume_data: Mapped[dict] = mapped_column(JSON, nullable=False)   # 结构化简历内容
    match_score: Mapped[int | None] = mapped_column(Integer)           # 匹配度 0-100
    highlights: Mapped[list] = mapped_column(JSON, default=list)      # 强匹配项
    gaps: Mapped[list] = mapped_column(JSON, default=list)            # 弱匹配/缺失项
    suggestions: Mapped[list] = mapped_column(JSON, default=list)     # AI 建议
    html_template: Mapped[str] = mapped_column(String(50), default="technical", nullable=False)
    # 生成时用户选的参数（模板/页数/语言/目标职级/侧重方向）。必须落库：
    # 重试要用同一套参数重跑，否则用户拿到的简历和当初选的完全不是一回事。
    preferences: Mapped[dict | None] = mapped_column(JSON)
    # AI 针对「JD 要求但档案缺失」给出的候选补强项目。**默认不进简历** ——
    # 由用户在前端逐条勾选确认后才合并进 resume_data。每一项都带 basis（推测依据）
    # 与 risk（风险等级），因为这类内容的本质是待核实草稿，不是事实陈述。
    enhancements: Mapped[list | None] = mapped_column(JSON)
    pdf_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)  # draft/pending/generated/exported/failed
    error_message: Mapped[str | None] = mapped_column(Text)  # 后台生成失败原因
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="resumes")
    jd: Mapped["JobDescription | None"] = relationship(back_populates="resumes")
    applications: Mapped[list["Application"]] = relationship(back_populates="resume")
    interview_prep: Mapped["InterviewPrep | None"] = relationship(
        back_populates="resume", uselist=False, cascade="all, delete-orphan"
    )
    versions: Mapped[list["ResumeVersion"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan", order_by="ResumeVersion.version_no"
    )
