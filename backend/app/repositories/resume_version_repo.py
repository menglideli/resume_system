"""简历版本快照 Repository。"""
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.models.resume_version import ResumeVersion
from app.repositories.base import BaseRepository


class ResumeVersionRepository(BaseRepository[ResumeVersion]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, ResumeVersion)

    async def list_meta_by_resume(self, resume_id: uuid.UUID) -> list[ResumeVersion]:
        """版本元信息列表（不带 resume_data 大字段），新→旧。"""
        stmt = (
            select(ResumeVersion)
            .options(load_only(
                ResumeVersion.id, ResumeVersion.resume_id, ResumeVersion.version_no,
                ResumeVersion.label, ResumeVersion.match_score, ResumeVersion.created_at,
            ))
            .where(ResumeVersion.resume_id == resume_id)
            .order_by(ResumeVersion.version_no.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_resume(self, resume_id: uuid.UUID, version_id: uuid.UUID) -> ResumeVersion | None:
        stmt = select(ResumeVersion).where(
            ResumeVersion.id == version_id, ResumeVersion.resume_id == resume_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def count_by_resume(self, resume_id: uuid.UUID) -> int:
        stmt = select(func.count(ResumeVersion.id)).where(ResumeVersion.resume_id == resume_id)
        return (await self.db.execute(stmt)).scalar_one()

    async def next_version_no(self, resume_id: uuid.UUID) -> int:
        stmt = select(func.max(ResumeVersion.version_no)).where(ResumeVersion.resume_id == resume_id)
        current = (await self.db.execute(stmt)).scalar_one_or_none()
        return (current or 0) + 1

    async def prune_oldest(self, resume_id: uuid.UUID, keep: int) -> int:
        """只保留最新 keep 条，返回删除条数。"""
        count = (await self.db.execute(
            select(func.count(ResumeVersion.id)).where(ResumeVersion.resume_id == resume_id)
        )).scalar_one()
        if count <= keep:
            return 0
        cutoff_stmt = (
            select(ResumeVersion.version_no)
            .where(ResumeVersion.resume_id == resume_id)
            .order_by(ResumeVersion.version_no.desc())
            .offset(keep - 1).limit(1)
        )
        cutoff = (await self.db.execute(cutoff_stmt)).scalar_one()
        result = await self.db.execute(
            delete(ResumeVersion).where(
                ResumeVersion.resume_id == resume_id, ResumeVersion.version_no < cutoff
            )
        )
        return result.rowcount or 0
