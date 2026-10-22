"""简历 Repository。"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.resume import Resume
from app.repositories.base import BaseRepository


class ResumeRepository(BaseRepository[Resume]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Resume)

    async def list_by_user(self, user_id: uuid.UUID, offset: int = 0, limit: int = 50) -> list[Resume]:
        stmt = (
            select(Resume)
            .options(selectinload(Resume.interview_prep))
            .where(Resume.user_id == user_id)
            .order_by(Resume.created_at.desc())
            .offset(offset).limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_user(self, resume_id: uuid.UUID, user_id: uuid.UUID) -> Resume | None:
        stmt = (
            select(Resume)
            .options(selectinload(Resume.interview_prep))
            .where(Resume.id == resume_id, Resume.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
