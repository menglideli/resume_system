"""用户档案表 ORM 模型（与 users 一对一）。"""
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    gender: Mapped[str | None] = mapped_column(String(10))
    birth_date: Mapped[date | None] = mapped_column(Date)
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(100))
    political_status: Mapped[str | None] = mapped_column(String(20))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text)
    custom_fields: Mapped[dict] = mapped_column(JSON, default=dict)  # 自定义字段 {字段名: 值}
    completeness_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="profile")
    educations: Mapped[list["Education"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="Education.order_index"
    )
    work_experiences: Mapped[list["WorkExperience"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="WorkExperience.order_index"
    )
    projects: Mapped[list["Project"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="Project.order_index"
    )
    skills: Mapped[list["Skill"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="Skill.order_index"
    )
    certifications: Mapped[list["Certification"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="Certification.order_index"
    )
    family_members: Mapped[list["FamilyMember"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    custom_blocks: Mapped[list["ProfileBlock"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="ProfileBlock.order_index"
    )
    field_defs: Mapped[list["CustomFieldDef"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="CustomFieldDef.order_index"
    )
