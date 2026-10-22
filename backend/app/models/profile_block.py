"""自定义信息块表 ORM 模型：块（字段定义）→ 条目（记录值）两级结构。"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy import JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProfileBlock(Base):
    """用户自定义信息块（如“父母信息”），fields 为字段定义数组。"""
    __tablename__ = "profile_blocks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    # 字段定义：[{name, label, type: text/number/date/textarea}]
    fields: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    profile: Mapped["Profile"] = relationship(back_populates="custom_blocks")
    entries: Mapped[list["ProfileBlockEntry"]] = relationship(
        back_populates="block", cascade="all, delete-orphan", order_by="ProfileBlockEntry.order_index"
    )


class ProfileBlockEntry(Base):
    """信息块内的一条记录（如“父亲”“母亲”各一条），data 为 {字段名: 值}。"""
    __tablename__ = "profile_block_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    block_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profile_blocks.id", ondelete="CASCADE"), index=True
    )
    data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    block: Mapped["ProfileBlock"] = relationship(back_populates="entries")
