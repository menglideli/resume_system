"""档案 Repository：含全量档案加载与子实体通用 CRUD。"""
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.profile import Profile
from app.models.profile_block import ProfileBlock
from app.repositories.base import BaseRepository


class ProfileRepository(BaseRepository[Profile]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Profile)

    async def get_by_user_id(self, user_id: uuid.UUID) -> Profile | None:
        result = await self.db.execute(select(Profile).where(Profile.user_id == user_id))
        return result.scalar_one_or_none()

    async def get_full_by_user_id(self, user_id: uuid.UUID) -> Profile | None:
        """一次性加载档案及全部子记录（避免 N+1）。"""
        stmt = (
            select(Profile)
            .where(Profile.user_id == user_id)
            .options(
                selectinload(Profile.educations),
                selectinload(Profile.work_experiences),
                selectinload(Profile.projects),
                selectinload(Profile.skills),
                selectinload(Profile.certifications),
                selectinload(Profile.family_members),
                selectinload(Profile.custom_blocks).selectinload(ProfileBlock.entries),
                selectinload(Profile.field_defs),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ---------- 子实体通用 CRUD（Education/WorkExperience/Project/...） ----------
    async def add_sub_entity(self, model: type, profile_id: uuid.UUID, data: dict[str, Any]):
        obj = model(profile_id=profile_id, **data)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def get_sub_entity(self, model: type, entity_id: uuid.UUID, profile_id: uuid.UUID):
        stmt = select(model).where(model.id == entity_id, model.profile_id == profile_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_sub_entity(self, model: type, entity_id: uuid.UUID, profile_id: uuid.UUID, data: dict[str, Any]):
        obj = await self.get_sub_entity(model, entity_id, profile_id)
        if obj is None:
            return None
        for key, value in data.items():
            setattr(obj, key, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def delete_sub_entity(self, model: type, entity_id: uuid.UUID, profile_id: uuid.UUID) -> bool:
        obj = await self.get_sub_entity(model, entity_id, profile_id)
        if obj is None:
            return False
        await self.db.delete(obj)
        await self.db.flush()
        return True
