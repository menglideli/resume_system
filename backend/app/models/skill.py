"""技能表 ORM 模型。"""
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, func
from sqlalchemy import JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50))
    proficiency: Mapped[int | None] = mapped_column(Integer)  # 熟练度 1-5
    custom_fields: Mapped[dict] = mapped_column(JSON, default=dict)  # 自定义字段 {字段名: 值}
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    visibility: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    profile: Mapped["Profile"] = relationship(back_populates="skills")
