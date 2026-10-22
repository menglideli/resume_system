"""认证路由：注册 / 登录（签发 JWT）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.common import success
from app.schemas.user import Token, UserLogin, UserRegister, UserResponse
from app.utils.dependencies import get_current_user
from app.utils.exceptions import ConflictException, UnauthorizedException
from app.utils.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", summary="用户注册")
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    if await repo.get_by_username(data.username):
        raise ConflictException("用户名已存在")
    if await repo.get_by_email(data.email):
        raise ConflictException("邮箱已被注册")
    user = await repo.create({
        "username": data.username,
        "email": data.email,
        "password_hash": hash_password(data.password),
    })
    await db.commit()
    return success(UserResponse.model_validate(user).model_dump(mode="json"), "注册成功")


@router.post("/login", response_model=None, summary="用户登录，返回 JWT")
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    user = await repo.get_by_username_or_email(data.username)
    if user is None or not verify_password(data.password, user.password_hash):
        raise UnauthorizedException("用户名或密码错误")
    token = create_access_token(str(user.id))
    return success(Token(access_token=token, is_admin=user.is_admin).model_dump(), "登录成功")


@router.get("/me", summary="当前登录用户信息")
async def me(user: User = Depends(get_current_user)):
    """前端启动时调用：既用于展示真实昵称/头像，也用于校验本地令牌是否仍然有效。

    关键：前端路由守卫只检查 localStorage 里有没有 token 字符串，伪造一个值就能绕过登录页。
    真正的拦截必须靠这里——令牌无效返回 401，前端据此清空本地令牌并跳回登录页。
    """
    return success(UserResponse.model_validate(user).model_dump(mode="json"))
