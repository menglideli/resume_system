"""后台管理业务层：用户管理 + 启动播种（初始管理员 / Kimi 配置导入）。"""
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.admin import AdminUserCreate, AdminUserUpdate
from app.services.config_service import KIMI_KEYS, ConfigService
from app.utils.exceptions import BadRequestException, ConflictException, NotFoundException
from app.utils.security import hash_password

logger = logging.getLogger("admin_service")

# .env 默认值来源（首次启动导入 system_config 用）
_ENV_KIMI_DEFAULTS = {
    "KIMI_API_KEY": lambda: settings.KIMI_API_KEY,
    "KIMI_BASE_URL": lambda: settings.KIMI_BASE_URL,
    "KIMI_MODEL": lambda: settings.KIMI_MODEL,
    "KIMI_TIMEOUT": lambda: str(settings.KIMI_TIMEOUT),
    "KIMI_MAX_TOKENS": lambda: str(settings.KIMI_MAX_TOKENS),
}


class AdminService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserRepository(db)

    # ---------------- 用户管理 ----------------
    async def list_users(self, keyword: str | None, offset: int, limit: int) -> list[User]:
        return await self.repo.list_users(keyword, offset, limit)

    async def create_user(self, data: AdminUserCreate) -> User:
        if await self.repo.get_by_username(data.username):
            raise ConflictException("用户名已存在")
        if await self.repo.get_by_email(data.email):
            raise ConflictException("邮箱已被注册")
        user = await self.repo.create({
            "username": data.username,
            "email": data.email,
            "password_hash": hash_password(data.password),
            "is_admin": data.is_admin,
        })
        await self.db.commit()
        return user

    async def _get_user(self, user_id: uuid.UUID) -> User:
        user = await self.repo.get(user_id)
        if user is None:
            raise NotFoundException("用户不存在")
        return user

    async def update_user(self, user_id: uuid.UUID, data: AdminUserUpdate) -> User:
        user = await self._get_user(user_id)
        updates: dict[str, Any] = {}
        if data.email is not None and data.email != user.email:
            if await self.repo.get_by_email(data.email):
                raise ConflictException("邮箱已被注册")
            updates["email"] = data.email
        if data.is_admin is not None:
            if user.is_admin and not data.is_admin and not await self._has_other_admin(user.id):
                raise BadRequestException("不能取消最后一个管理员的管理权限")
            updates["is_admin"] = data.is_admin
        if updates:
            await self.repo.update(user, updates)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def reset_password(self, user_id: uuid.UUID, new_password: str) -> None:
        user = await self._get_user(user_id)
        await self.repo.update(user, {"password_hash": hash_password(new_password)})
        await self.db.commit()

    async def delete_user(self, user_id: uuid.UUID, operator_id: uuid.UUID) -> None:
        if user_id == operator_id:
            raise BadRequestException("不能删除当前登录的管理员账号")
        user = await self._get_user(user_id)
        if user.is_admin and not await self._has_other_admin(user.id):
            raise BadRequestException("不能删除最后一个管理员")
        await self.repo.delete(user)  # 档案/简历/表单等随外键级联删除
        await self.db.commit()

    async def _has_other_admin(self, exclude_id: uuid.UUID) -> bool:
        admins = await self.repo.list_users(limit=1000)
        return any(u.is_admin and u.id != exclude_id for u in admins)


# ---------------- 启动播种 ----------------
async def seed_initial_data() -> None:
    """首次启动：创建初始管理员，并把 .env 的 Kimi 配置导入 system_config（已有值不覆盖）。"""
    async with AsyncSessionLocal() as db:
        repo = UserRepository(db)
        if not await repo.has_admin():
            await repo.create({
                "username": "admin",
                "email": "admin@localhost",
                "password_hash": hash_password(settings.ADMIN_DEFAULT_PASSWORD),
                "is_admin": True,
            })
            logger.info("已创建初始管理员账号 admin")

        cfg = ConfigService(db)
        for key in KIMI_KEYS:
            if await cfg.get(key) is None:
                value = _ENV_KIMI_DEFAULTS[key]()
                if value:  # 空值不写入，保持回退 .env 的语义
                    await cfg.set(key, value)
        await db.commit()
