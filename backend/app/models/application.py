"""投递记录表 ORM 模型。"""
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    resume_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("resumes.id", ondelete="SET NULL"))
    jd_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("job_descriptions.id", ondelete="SET NULL"))
    company_name: Mapped[str] = mapped_column(String(100), nullable=False)
    position_title: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="website", nullable=False)  # email/website/official
    status: Mapped[str] = mapped_column(String(20), default="applied", nullable=False, index=True)  # applied/viewed/interview/offer/rejected
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text)
    follow_up_date: Mapped[date | None] = mapped_column(Date, index=True)
    # ---- 投递版本锁定：招聘方看到的是投递当时的版本，快照必须与后续编辑解耦 ----
    resume_snapshot: Mapped[dict | None] = mapped_column(JSON)          # 投递时的 resume_data（已过滤）
    snapshot_template: Mapped[str | None] = mapped_column(String(50))   # 投递时使用的模板
    snapshot_pdf_path: Mapped[str | None] = mapped_column(String(500))  # 复制出的 PDF 副本路径
    snapshot_match_score: Mapped[int | None] = mapped_column(Integer)
    jd_snapshot: Mapped[dict | None] = mapped_column(JSON)              # {raw_text, parsed_data, company, position}

    user: Mapped["User"] = relationship(back_populates="applications")
    resume: Mapped["Resume | None"] = relationship(back_populates="applications")
    jd: Mapped["JobDescription | None"] = relationship()
