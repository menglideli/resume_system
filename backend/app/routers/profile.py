"""用户档案路由：基础信息 + 六类子资源 CRUD（指令 5 路由 4）。"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.certification import CertificationCreate, CertificationUpdate
from app.schemas.common import success
from app.schemas.custom_field_def import FieldDefCreate, FieldDefResponse, FieldDefUpdate
from app.schemas.education import EducationCreate, EducationUpdate
from app.schemas.family import FamilyCreate, FamilyUpdate
from app.schemas.profile import ProfileFullResponse, ProfileResponse, ProfileUpdate
from app.schemas.profile_block import (
    BlockCreate, BlockEntryCreate, BlockEntryResponse, BlockResponse, BlockUpdate,
)
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.schemas.skill import SkillCreate, SkillUpdate
from app.schemas.work import WorkCreate, WorkUpdate
from app.services.profile_service import ProfileService
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/profile", tags=["用户档案"])

# 子资源路径段 → (CreateSchema, UpdateSchema)
SUB_RESOURCES = {
    "educations": (EducationCreate, EducationUpdate),
    "work-experiences": (WorkCreate, WorkUpdate),
    "projects": (ProjectCreate, ProjectUpdate),
    "skills": (SkillCreate, SkillUpdate),
    "certifications": (CertificationCreate, CertificationUpdate),
    "family-members": (FamilyCreate, FamilyUpdate),
}


@router.get("", summary="获取当前用户完整档案")
async def get_profile(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profile = await ProfileService(db).get_full_profile(user.id)
    return success(ProfileFullResponse.model_validate(profile).model_dump(mode="json"))


@router.put("", summary="更新档案基础信息")
async def update_profile(data: ProfileUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profile = await ProfileService(db).update_profile(user.id, data)
    return success(ProfileResponse.model_validate(profile).model_dump(mode="json"), "更新成功")


# ---------------- 自定义信息块（块 → 条目两级） ----------------
@router.get("/blocks", summary="获取全部自定义信息块（含条目）")
async def list_blocks(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    blocks = await ProfileService(db).list_blocks(user.id)
    return success([BlockResponse.model_validate(b).model_dump(mode="json") for b in blocks])


@router.post("/blocks", summary="新建信息块（先定义块名与字段）")
async def create_block(data: BlockCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    fields = [f.model_dump() for f in data.fields]
    for f in fields:
        f["label"] = f.get("label") or f["name"]
    block = await ProfileService(db).create_block(user.id, data.name, fields)
    return success(BlockResponse.model_validate(block).model_dump(mode="json"), "创建成功")


@router.put("/blocks/{block_id}", summary="更新信息块（改名/调整字段定义）")
async def update_block(
    block_id: uuid.UUID, data: BlockUpdate,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    fields = None
    if data.fields is not None:
        fields = [f.model_dump() for f in data.fields]
        for f in fields:
            f["label"] = f.get("label") or f["name"]
    block = await ProfileService(db).update_block(user.id, block_id, data.name, fields)
    return success(BlockResponse.model_validate(block).model_dump(mode="json"), "更新成功")


@router.delete("/blocks/{block_id}", summary="删除信息块（含全部条目）")
async def delete_block(
    block_id: uuid.UUID,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await ProfileService(db).delete_block(user.id, block_id)
    return success(None, "删除成功")


@router.post("/blocks/{block_id}/entries", summary="在信息块中添加一条记录")
async def add_block_entry(
    block_id: uuid.UUID, data: BlockEntryCreate,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    entry = await ProfileService(db).add_entry(user.id, block_id, data.data)
    return success(BlockEntryResponse.model_validate(entry).model_dump(mode="json"), "添加成功")


@router.put("/blocks/{block_id}/entries/{entry_id}", summary="更新信息块记录")
async def update_block_entry(
    block_id: uuid.UUID, entry_id: uuid.UUID, data: BlockEntryCreate,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    entry = await ProfileService(db).update_entry(user.id, block_id, entry_id, data.data)
    return success(BlockEntryResponse.model_validate(entry).model_dump(mode="json"), "更新成功")


@router.delete("/blocks/{block_id}/entries/{entry_id}", summary="删除信息块记录")
async def delete_block_entry(
    block_id: uuid.UUID, entry_id: uuid.UUID,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await ProfileService(db).delete_entry(user.id, block_id, entry_id)
    return success(None, "删除成功")


# ---------------- 自定义字段定义（各版块随时加字段） ----------------
@router.get("/field-defs", summary="获取全部自定义字段定义")
async def list_field_defs(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    defs = await ProfileService(db).list_field_defs(user.id)
    return success([FieldDefResponse.model_validate(d).model_dump(mode="json") for d in defs])


@router.post("/field-defs", summary="为版块添加自定义字段")
async def create_field_def(data: FieldDefCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    field_def = await ProfileService(db).create_field_def(
        user.id, data.section, data.name, data.label, data.type
    )
    return success(FieldDefResponse.model_validate(field_def).model_dump(mode="json"), "添加成功")


@router.put("/field-defs/{def_id}", summary="修改自定义字段（显示名/类型）")
async def update_field_def(
    def_id: uuid.UUID, data: FieldDefUpdate,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    field_def = await ProfileService(db).update_field_def(user.id, def_id, data.label, data.type)
    return success(FieldDefResponse.model_validate(field_def).model_dump(mode="json"), "更新成功")


@router.delete("/field-defs/{def_id}", summary="删除自定义字段定义")
async def delete_field_def(
    def_id: uuid.UUID,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await ProfileService(db).delete_field_def(user.id, def_id)
    return success(None, "删除成功")


def _register_sub_routes():
    """为六类子资源注册 POST/PUT/DELETE（结构一致，循环生成）。"""
    for resource, (create_schema, update_schema) in SUB_RESOURCES.items():

        async def add(
            data: create_schema,  # type: ignore[valid-type]
            user: User = Depends(get_current_user),
            db: AsyncSession = Depends(get_db),
            _resource: str = resource,
        ):
            obj = await ProfileService(db).add_sub_entity(user.id, _resource, data.model_dump())
            return success(_dump(obj), "添加成功")

        async def update(
            entity_id: uuid.UUID,
            data: update_schema,  # type: ignore[valid-type]
            user: User = Depends(get_current_user),
            db: AsyncSession = Depends(get_db),
            _resource: str = resource,
        ):
            obj = await ProfileService(db).update_sub_entity(
                user.id, _resource, entity_id, data.model_dump(exclude_unset=True)
            )
            return success(_dump(obj), "更新成功")

        async def delete(
            entity_id: uuid.UUID,
            user: User = Depends(get_current_user),
            db: AsyncSession = Depends(get_db),
            _resource: str = resource,
        ):
            await ProfileService(db).delete_sub_entity(user.id, _resource, entity_id)
            return success(None, "删除成功")

        router.post(f"/{resource}", summary=f"添加{resource}")(add)
        router.put(f"/{resource}/{{entity_id}}", summary=f"更新{resource}")(update)
        router.delete(f"/{resource}/{{entity_id}}", summary=f"删除{resource}")(delete)


def _dump(obj) -> dict:
    """ORM → dict（通用列序列化，UUID/date/datetime 转字符串）。"""
    result = {}
    for c in obj.__table__.columns:
        value = getattr(obj, c.name)
        if value is not None and not isinstance(value, (str, int, float, bool, list, dict)):
            value = str(value)
        result[c.name] = value
    return result


_register_sub_routes()
