"""后台管理路由：用户管理 + 系统配置（仅管理员）。"""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.admin import (
    AdminUserCreate, AdminUserResponse, AdminUserUpdate, ResetPassword, SystemConfigUpdate,
)
from app.schemas.common import success
from app.services.admin_service import AdminService
from app.services.config_service import ConfigService
from app.utils.dependencies import require_admin

router = APIRouter(prefix="/admin", tags=["后台管理"], dependencies=[Depends(require_admin)])


# ---------------- 用户管理 ----------------
@router.get("/users", summary="用户列表（支持关键字搜索）")
async def list_users(
    keyword: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    users = await AdminService(db).list_users(keyword, offset, limit)
    return success([AdminUserResponse.model_validate(u).model_dump(mode="json") for u in users])


@router.post("/users", summary="创建用户")
async def create_user(data: AdminUserCreate, db: AsyncSession = Depends(get_db)):
    user = await AdminService(db).create_user(data)
    return success(AdminUserResponse.model_validate(user).model_dump(mode="json"), "创建成功")


@router.put("/users/{user_id}", summary="更新用户（邮箱/角色）")
async def update_user(user_id: uuid.UUID, data: AdminUserUpdate, db: AsyncSession = Depends(get_db)):
    user = await AdminService(db).update_user(user_id, data)
    return success(AdminUserResponse.model_validate(user).model_dump(mode="json"), "更新成功")


@router.delete("/users/{user_id}", summary="删除用户（级联删除其全部数据）")
async def delete_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await AdminService(db).delete_user(user_id, admin.id)
    return success(None, "删除成功")


@router.post("/users/{user_id}/reset-password", summary="重置用户密码")
async def reset_password(user_id: uuid.UUID, data: ResetPassword, db: AsyncSession = Depends(get_db)):
    await AdminService(db).reset_password(user_id, data.new_password)
    return success(None, "密码已重置")


# ---------------- 系统配置 ----------------
@router.get("/config", summary="获取系统配置（API Key 掩码）")
async def get_config(db: AsyncSession = Depends(get_db)):
    return success(await ConfigService(db).get_kimi_config_masked())


@router.put("/config", summary="更新系统配置（立即生效，无需重启）")
async def update_config(data: SystemConfigUpdate, db: AsyncSession = Depends(get_db)):
    cfg = await ConfigService(db).update_kimi_config(data.model_dump(exclude_unset=True))
    return success(cfg, "配置已更新")
