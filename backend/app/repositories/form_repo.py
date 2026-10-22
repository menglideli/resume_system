"""报名表 Repository。"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.form import FormModel
from app.repositories.base import BaseRepository


class FormRepository(BaseRepository[FormModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, FormModel)

    async def list_by_user(self, user_id: uuid.UUID, offset: int = 0, limit: int = 50) -> list[FormModel]:
        stmt = (
            select(FormModel)
            .where(FormModel.user_id == user_id)
            .order_by(FormModel.created_at.desc())
            .offset(offset).limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_user(self, form_id: uuid.UUID, user_id: uuid.UUID) -> FormModel | None:
        stmt = select(FormModel).where(FormModel.id == form_id, FormModel.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
