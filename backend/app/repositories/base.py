"""泛型 Repository：提供单实体 CRUD，子类指定 model 即可复用。"""
import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    def __init__(self, db: AsyncSession, model: type[ModelT]):
        self.db = db
        self.model = model

    async def get(self, id: uuid.UUID) -> ModelT | None:
        return await self.db.get(self.model, id)

    async def get_multi(self, *, offset: int = 0, limit: int = 100, **filters: Any) -> list[ModelT]:
        stmt = select(self.model)
        for key, value in filters.items():
            if value is not None:
                stmt = stmt.where(getattr(self.model, key) == value)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, obj_in: dict[str, Any]) -> ModelT:
        obj = self.model(**obj_in)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def update(self, obj: ModelT, obj_in: dict[str, Any]) -> ModelT:
        for key, value in obj_in.items():
            if value is not None or key in obj_in:
                setattr(obj, key, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj: ModelT) -> None:
        await self.db.delete(obj)
        await self.db.flush()
