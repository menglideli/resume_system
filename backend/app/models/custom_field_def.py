"""自定义字段定义表：每个档案版块可由用户自行追加字段（预制于数据库，随时增删）。"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CustomFieldDef(Base):
    __tablename__ = "custom_field_defs"
    __table_args__ = (
        UniqueConstraint("profile_id", "section", "name", name="uk_field_def"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    # basic / educations / work-experiences / projects / skills / certifications / family-members
    section: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)    # 字段键（英文）
    label: Mapped[str] = mapped_column(String(50), nullable=False)   # 显示名
    type: Mapped[str] = mapped_column(String(20), default="text", nullable=False)  # text/number/date/textarea
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["Profile"] = relationship(back_populates="field_defs")
