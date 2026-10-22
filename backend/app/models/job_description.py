"""岗位描述表 ORM 模型。"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy import JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    company_name: Mapped[str | None] = mapped_column(String(100))
    position_title: Mapped[str | None] = mapped_column(String(100))
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)        # 原始 JD 文本
    parsed_data: Mapped[dict | None] = mapped_column(JSON)            # AI 解析结果
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="job_descriptions")
    resumes: Mapped[list["Resume"]] = relationship(back_populates="jd")
