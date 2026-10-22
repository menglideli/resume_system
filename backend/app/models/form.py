"""报名表 ORM 模型（类名 FormModel 避免与 fastapi.Form 冲突）。"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy import JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FormModel(Base):
    __tablename__ = "forms"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)      # pdf/word/excel
    form_structure: Mapped[dict | None] = mapped_column(JSON)              # 解析出的字段结构
    field_mapping: Mapped[dict | None] = mapped_column(JSON)               # 字段映射关系
    filled_data: Mapped[dict | None] = mapped_column(JSON)                 # 实际填充数据
    status: Mapped[str] = mapped_column(String(20), default="uploaded", nullable=False)  # uploaded/analyzed/mapped/filled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="forms")
