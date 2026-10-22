"""FastAPI 公共依赖：JWT 认证、当前用户注入。"""
import uuid

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.utils.exceptions import ForbiddenException, UnauthorizedException
from app.utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """解析 Bearer JWT，返回当前登录用户；未认证抛 401。"""
    if not token:
        raise UnauthorizedException("缺少认证令牌")
    subject = decode_access_token(token)
    if not subject:
        raise UnauthorizedException("令牌无效或已过期")
    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        raise UnauthorizedException("令牌内容非法")
    user = await UserRepository(db).get(user_id)
    if user is None:
        raise UnauthorizedException("用户不存在")
    return user


async def get_current_user_id(user: User = Depends(get_current_user)) -> uuid.UUID:
    return user.id


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """仅管理员可访问；非管理员抛 403。"""
    if not user.is_admin:
        raise ForbiddenException("需要管理员权限")
    return user
