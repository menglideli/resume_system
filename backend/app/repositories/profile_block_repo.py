"""自定义信息块 Repository：块与条目两级结构的数据访问。"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.profile_block import ProfileBlock, ProfileBlockEntry
from app.repositories.base import BaseRepository


class ProfileBlockRepository(BaseRepository[ProfileBlock]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, ProfileBlock)

    async def list_by_profile(self, profile_id: uuid.UUID) -> list[ProfileBlock]:
        stmt = (
            select(ProfileBlock)
            .where(ProfileBlock.profile_id == profile_id)
            .options(selectinload(ProfileBlock.entries))
            .order_by(ProfileBlock.order_index)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_owned(self, block_id: uuid.UUID, profile_id: uuid.UUID) -> ProfileBlock | None:
        stmt = (
            select(ProfileBlock)
            .where(ProfileBlock.id == block_id, ProfileBlock.profile_id == profile_id)
            .options(selectinload(ProfileBlock.entries))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ---------- 条目 ----------
    async def add_entry(self, block_id: uuid.UUID, data: dict) -> ProfileBlockEntry:
        entry = ProfileBlockEntry(block_id=block_id, data=data)
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)
        return entry

    async def get_entry(self, entry_id: uuid.UUID, block_id: uuid.UUID) -> ProfileBlockEntry | None:
        stmt = select(ProfileBlockEntry).where(
            ProfileBlockEntry.id == entry_id, ProfileBlockEntry.block_id == block_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_entry(self, entry_id: uuid.UUID, block_id: uuid.UUID, data: dict) -> ProfileBlockEntry | None:
        entry = await self.get_entry(entry_id, block_id)
        if entry is None:
            return None
        entry.data = data
        await self.db.flush()
        await self.db.refresh(entry)
        return entry

    async def delete_entry(self, entry_id: uuid.UUID, block_id: uuid.UUID) -> bool:
        entry = await self.get_entry(entry_id, block_id)
        if entry is None:
            return False
        await self.db.delete(entry)
        await self.db.flush()
        return True
