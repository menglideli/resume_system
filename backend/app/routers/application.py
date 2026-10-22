"""投递管理路由（指令 8）。"""
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.application import (
    ApplicationCreate, ApplicationListResponse, ApplicationResponse,
    ApplicationSnapshotResponse, ApplicationStats, ApplicationUpdate,
)
from app.schemas.common import success
from app.services.application_service import ApplicationService
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/applications", tags=["投递管理"])


@router.post("", summary="创建投递记录")
async def create_application(data: ApplicationCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    app = await ApplicationService(db).create(user.id, data)
    return success(ApplicationResponse.model_validate(app).model_dump(mode="json"), "创建成功")


@router.get("", summary="投递列表（status/channel/时间范围筛选）")
async def list_applications(
    status: str | None = Query(None), channel: str | None = Query(None),
    date_from: date | None = Query(None), date_to: date | None = Query(None),
    offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    total, items = await ApplicationService(db).list(user.id, status, channel, date_from, date_to, offset, limit)
    return success(ApplicationListResponse(
        total=total,
        items=[ApplicationResponse.model_validate(i).model_dump(mode="json") for i in items],
    ).model_dump(mode="json"))


@router.get("/stats", summary="投递统计")
async def application_stats(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stats = await ApplicationService(db).stats(user.id)
    return success(ApplicationStats(**stats).model_dump())


@router.get("/follow-ups", summary="需要跟进的投递")
async def follow_ups(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    items = await ApplicationService(db).follow_ups(user.id)
    return success([ApplicationResponse.model_validate(i).model_dump(mode="json") for i in items])


@router.get("/{app_id}", summary="投递详情")
async def get_application(app_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    app = await ApplicationService(db).get(app_id, user.id)
    return success(ApplicationResponse.model_validate(app).model_dump(mode="json"))


@router.get("/{app_id}/snapshot", summary="投递版本快照（招聘方当时看到的简历与 JD）")
async def get_application_snapshot(app_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    app = await ApplicationService(db).get_snapshot(app_id, user.id)
    return success(ApplicationSnapshotResponse.model_validate(app).model_dump(mode="json"))


@router.get("/{app_id}/snapshot/pdf", summary="下载投递时锁定的 PDF 副本")
async def download_application_snapshot_pdf(app_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """返回原始文件流（非信封）：前端用 apiDownload 取 blob。"""
    pdf_path = await ApplicationService(db).snapshot_pdf_path(app_id, user.id)
    return FileResponse(pdf_path, media_type="application/pdf", filename=Path(pdf_path).name)


@router.put("/{app_id}", summary="更新投递状态")
async def update_application(app_id: uuid.UUID, data: ApplicationUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    app = await ApplicationService(db).update(app_id, user.id, data)
    return success(ApplicationResponse.model_validate(app).model_dump(mode="json"), "更新成功")


@router.delete("/{app_id}", summary="删除投递记录")
async def delete_application(app_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await ApplicationService(db).delete(app_id, user.id)
    return success(None, "删除成功")
