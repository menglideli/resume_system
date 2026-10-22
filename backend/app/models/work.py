"""工作经历表 ORM 模型。"""
import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, func
from sqlalchemy import JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WorkExperience(Base):
    __tablename__ = "work_experiences"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    company: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[str | None] = mapped_column(String(100))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[list] = mapped_column(JSON, default=list)    # bullet points 数组
    achievements: Mapped[list] = mapped_column(JSON, default=list)   # 量化成果数组
    custom_fields: Mapped[dict] = mapped_column(JSON, default=dict)  # 自定义字段 {字段名: 值}
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    visibility: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    profile: Mapped["Profile"] = relationship(back_populates="work_experiences")
