"""面试准备表 ORM 模型：一份简历一条，持久化 AI 生成的岗位调研/面试提纲/题库。"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy import JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InterviewPrep(Base):
    __tablename__ = "interview_preps"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), unique=True, index=True
    )
    research: Mapped[dict] = mapped_column(JSON, default=dict)    # 岗位调研
    outline: Mapped[dict] = mapped_column(JSON, default=dict)     # 面试提纲
    questions: Mapped[list] = mapped_column(JSON, default=list)   # 题库 [{type, question, reference_answer, key_points}]
    # 三段 AI 调用串行执行耗时数分钟，改后台任务后用状态位驱动前端轮询
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    resume: Mapped["Resume"] = relationship(back_populates="interview_prep")
