"""JD 解析路由（指令 5 路由 1）。"""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.common import success
from app.schemas.job_description import JDParseRequest, JDResponse
from app.services.jd_service import JDService
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/jd", tags=["JD 解析"])


@router.post("/parse", summary="解析岗位描述 JD")
async def parse_jd(data: JDParseRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """AI 深度解析 JD，返回结构化结果与匹配预览。"""
    jd, preview = await JDService(db).parse_and_save(user.id, data.raw_text, data.company_name, data.position_title)
    return success({
        "id": str(jd.id),
        "parsed_data": jd.parsed_data,
        "match_preview": preview,
    })


@router.get("/list", summary="JD 列表")
async def list_jd(
    offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    items = await JDService(db).list(user.id, offset, limit)
    return success([JDResponse.model_validate(i).model_dump(mode="json") for i in items])


@router.get("/{jd_id}", summary="JD 详情")
async def get_jd(jd_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    jd = await JDService(db).get(jd_id, user.id)
    return success(JDResponse.model_validate(jd).model_dump(mode="json"))


@router.delete("/{jd_id}", summary="删除 JD")
async def delete_jd(jd_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await JDService(db).delete(jd_id, user.id)
    return success(None, "删除成功")
