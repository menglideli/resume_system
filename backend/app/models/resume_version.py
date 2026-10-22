"""简历内容版本快照表：每次内容落地追加一行，当前 resume_data 永远等于最新版本。"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy import JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ResumeVersion(Base):
    __tablename__ = "resume_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)   # 每份简历内从 1 递增
    # ai_generated / user_edit / enhancement_applied / rollback
    label: Mapped[str] = mapped_column(String(30), nullable=False)
    resume_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    match_score: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    resume: Mapped["Resume"] = relationship(back_populates="versions")
