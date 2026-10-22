"""照片表 ORM 模型：用户私有照片库（工作照 / 生活照等分类）。"""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(30), default="work", nullable=False, index=True)  # work/life/other
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)   # 服务器存储路径（UUID 化）
    mime_type: Mapped[str | None] = mapped_column(String(100))
    size: Mapped[int | None] = mapped_column(BigInteger)                    # 字节
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
