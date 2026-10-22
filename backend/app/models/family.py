"""家庭成员表 ORM 模型（报名表填写用）。"""
import uuid

from sqlalchemy import ForeignKey, String, func
from sqlalchemy import JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship as orm_relationship  # 避免与字段名 relationship 冲突

from app.database import Base


class FamilyMember(Base):
    __tablename__ = "family_members"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    relationship: Mapped[str | None] = mapped_column(String(20))   # 父子/母子/配偶...
    work_unit: Mapped[str | None] = mapped_column(String(100))
    position: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(20))
    custom_fields: Mapped[dict] = mapped_column(JSON, default=dict)  # 自定义字段 {字段名: 值}

    profile: Mapped["Profile"] = orm_relationship(back_populates="family_members")
