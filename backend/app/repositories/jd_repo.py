"""JD Repository。"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_description import JobDescription
from app.repositories.base import BaseRepository


class JDRepository(BaseRepository[JobDescription]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, JobDescription)

    async def list_by_user(self, user_id: uuid.UUID, offset: int = 0, limit: int = 50) -> list[JobDescription]:
        stmt = (
            select(JobDescription)
            .where(JobDescription.user_id == user_id)
            .order_by(JobDescription.created_at.desc())
            .offset(offset).limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
