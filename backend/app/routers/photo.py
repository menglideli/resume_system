"""照片库路由：上传 / 列表 / 预览下载 / 删除。"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Query, UploadFile
from fastapi import File as FastAPIFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.common import success
from app.schemas.photo import PhotoResponse
from app.services.photo_service import PhotoService
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/photos", tags=["照片库"])


@router.post("/upload", summary="上传照片（分类：work 工作 / life 生活 / other 其他）")
async def upload_photo(
    file: UploadFile = FastAPIFile(..., description="jpg/jpeg/png/gif/webp/bmp"),
    category: str = Form("other", description="分类：work 工作 / life 生活 / other 其他"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await file.read()
    photo = await PhotoService(db).upload(user.id, file.filename or "photo", data, category)
    return success(PhotoResponse.model_validate(photo).model_dump(mode="json"), "上传成功")


@router.get("", summary="照片列表（可按分类过滤）")
async def list_photos(
    category: str | None = Query(None),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    items = await PhotoService(db).list(user.id, category)
    return success([PhotoResponse.model_validate(i).model_dump(mode="json") for i in items])


@router.get("/{photo_id}/file", summary="获取照片原图（鉴权，前端经 blob 展示）")
async def get_photo_file(photo_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    path, mime = await PhotoService(db).get_file(photo_id, user.id)
    return FileResponse(path, media_type=mime or "application/octet-stream", filename=Path(path).name)


@router.delete("/{photo_id}", summary="删除照片（记录与文件一并删除）")
async def delete_photo(photo_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await PhotoService(db).delete(photo_id, user.id)
    return success(None, "删除成功")
