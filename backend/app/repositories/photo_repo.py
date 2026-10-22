"""照片 Repository。"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.photo import Photo
from app.repositories.base import BaseRepository


class PhotoRepository(BaseRepository[Photo]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Photo)

    async def list_by_user(self, user_id: uuid.UUID, category: str | None = None) -> list[Photo]:
        stmt = select(Photo).where(Photo.user_id == user_id)
        if category:
            stmt = stmt.where(Photo.category == category)
        stmt = stmt.order_by(Photo.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_user(self, photo_id: uuid.UUID, user_id: uuid.UUID) -> Photo | None:
        stmt = select(Photo).where(Photo.id == photo_id, Photo.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
