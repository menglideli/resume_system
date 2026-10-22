"""报名表路由（指令 5 路由 5 / 指令 7 处理接口）。"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi import File as FastAPIFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.common import success
from app.schemas.form import FormMappingRequest, FormResponse
from app.services.form_service import FormService
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/forms", tags=["报名表"])


@router.post("/upload", summary="上传报名表文件")
async def upload_form(
    file: UploadFile = FastAPIFile(..., description="pdf / doc / docx / xls / xlsx"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await file.read()
    form = await FormService(db).upload(user.id, file.filename or "unknown", data)
    return success(FormResponse.model_validate(form).model_dump(mode="json"), "上传成功")


@router.get("", summary="报名表列表")
async def list_forms(
    offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    items = await FormService(db).list(user.id, offset, limit)
    return success([FormResponse.model_validate(i).model_dump(mode="json") for i in items])


@router.get("/{form_id}/analysis", summary="获取 AI 识别的表单结构")
async def analyze_form(form_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    structure = await FormService(db).analyze(form_id, user.id)
    return success(structure)


@router.post("/{form_id}/mapping", summary="AI 字段映射（可传 mappings 人工覆盖）")
async def map_form(form_id: uuid.UUID, data: FormMappingRequest | None = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    manual = [m.model_dump() for m in data.mappings] if data and data.mappings else None
    result = await FormService(db).build_mapping(form_id, user.id, manual)
    return success(result)


@router.post("/{form_id}/fill", summary="执行自动填充")
async def fill_form(form_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    filled_path, mapping_data = await FormService(db).fill(form_id, user.id)
    return success({"filled_path": filled_path, "filled_data": mapping_data}, "填充完成")


@router.get("/{form_id}/download", summary="下载填充后的文件")
async def download_form(form_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    path = await FormService(db).get_download_path(form_id, user.id)
    suffix = Path(path).suffix.lstrip(".")
    media_type = {"pdf": "application/pdf", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                  "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}.get(suffix, "text/plain")
    return FileResponse(path, media_type=media_type, filename=Path(path).name)


@router.delete("/{form_id}", summary="删除报名表")
async def delete_form(form_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await FormService(db).delete(form_id, user.id)
    return success(None, "删除成功")
