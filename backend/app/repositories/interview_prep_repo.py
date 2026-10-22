"""面试准备 Repository。"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interview_prep import InterviewPrep
from app.repositories.base import BaseRepository


class InterviewPrepRepository(BaseRepository[InterviewPrep]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, InterviewPrep)

    async def get_by_resume(self, resume_id: uuid.UUID) -> InterviewPrep | None:
        stmt = select(InterviewPrep).where(InterviewPrep.resume_id == resume_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
