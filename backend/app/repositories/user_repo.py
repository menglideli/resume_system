"""用户 Repository。"""
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, User)

    async def get_by_username(self, username: str) -> User | None:
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_username_or_email(self, account: str) -> User | None:
        result = await self.db.execute(
            select(User).where(or_(User.username == account, User.email == account))
        )
        return result.scalar_one_or_none()

    async def list_users(self, keyword: str | None = None, offset: int = 0, limit: int = 100) -> list[User]:
        """后台用户列表：可选用户名/邮箱关键字搜索。"""
        stmt = select(User).order_by(User.created_at.desc())
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(or_(User.username.like(like), User.email.like(like)))
        result = await self.db.execute(stmt.offset(offset).limit(limit))
        return list(result.scalars().all())

    async def has_admin(self) -> bool:
        result = await self.db.execute(select(User.id).where(User.is_admin.is_(True)).limit(1))
        return result.scalar_one_or_none() is not None
