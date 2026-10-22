"""自定义字段定义 Repository：档案各版块追加字段定义的数据访问。"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.custom_field_def import CustomFieldDef
from app.repositories.base import BaseRepository


class CustomFieldDefRepository(BaseRepository[CustomFieldDef]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, CustomFieldDef)

    async def list_by_profile(self, profile_id: uuid.UUID) -> list[CustomFieldDef]:
        stmt = (
            select(CustomFieldDef)
            .where(CustomFieldDef.profile_id == profile_id)
            .order_by(CustomFieldDef.section, CustomFieldDef.order_index)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_owned(self, def_id: uuid.UUID, profile_id: uuid.UUID) -> CustomFieldDef | None:
        stmt = select(CustomFieldDef).where(
            CustomFieldDef.id == def_id, CustomFieldDef.profile_id == profile_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def exists(self, profile_id: uuid.UUID, section: str, name: str) -> bool:
        stmt = select(CustomFieldDef.id).where(
            CustomFieldDef.profile_id == profile_id,
            CustomFieldDef.section == section,
            CustomFieldDef.name == name,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None
