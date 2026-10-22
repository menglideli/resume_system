"""用户档案业务层：CRUD + 子实体管理 + 完整性评分。"""
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Certification, Education, FamilyMember, Profile, Project, Skill, WorkExperience,
)
from app.models.custom_field_def import CustomFieldDef
from app.models.profile_block import ProfileBlock
from app.repositories.custom_field_def_repo import CustomFieldDefRepository
from app.repositories.profile_block_repo import ProfileBlockRepository
from app.repositories.profile_repo import ProfileRepository
from app.schemas.custom_field_def import SECTIONS
from app.schemas.profile import ProfileUpdate
from app.utils.exceptions import BadRequestException, NotFoundException

# 子资源名 → ORM 模型
SUB_ENTITY_MODELS = {
    "educations": Education,
    "work-experiences": WorkExperience,
    "projects": Project,
    "skills": Skill,
    "certifications": Certification,
    "family-members": FamilyMember,
}

# 各版块固定字段（自定义字段不得与之重名）
FIXED_FIELDS = {
    "basic": {
        "name", "gender", "birth_date", "phone", "email", "location",
        "political_status", "avatar_url", "summary", "completeness_score",
    },
    "educations": {
        "school", "major", "degree", "start_date", "end_date", "gpa",
        "courses", "is_current", "order_index", "visibility", "priority",
    },
    "work-experiences": {
        "company", "position", "start_date", "end_date", "description",
        "achievements", "is_current", "order_index", "visibility", "priority",
    },
    "projects": {
        "name", "role", "tech_stack", "start_date", "end_date", "description",
        "highlights", "url", "order_index", "visibility", "priority",
    },
    "skills": {"name", "category", "proficiency", "order_index", "visibility"},
    "certifications": {
        "name", "issuer", "issue_date", "expiry_date", "credential_id",
        "order_index", "visibility",
    },
    "family-members": {"name", "relationship", "work_unit", "position", "phone"},
}


class ProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ProfileRepository(db)

    async def get_or_create_profile(self, user_id: uuid.UUID) -> Profile:
        profile = await self.repo.get_by_user_id(user_id)
        if profile is None:
            profile = await self.repo.create({"user_id": user_id})
            await self.db.commit()
        return profile

    async def get_full_profile(self, user_id: uuid.UUID) -> Profile:
        await self.get_or_create_profile(user_id)
        profile = await self.repo.get_full_by_user_id(user_id)
        if profile is None:
            raise NotFoundException("档案不存在")
        return profile

    async def update_profile(self, user_id: uuid.UUID, data: ProfileUpdate) -> Profile:
        profile = await self.get_or_create_profile(user_id)
        await self.repo.update(profile, data.model_dump(exclude_unset=True))
        profile.completeness_score = await self._calc_completeness(profile.id)
        await self.db.commit()
        await self.db.refresh(profile)
        return profile

    # ---------- 子实体 ----------
    async def add_sub_entity(self, user_id: uuid.UUID, resource: str, data: dict[str, Any]):
        model = self._model_of(resource)
        profile = await self.get_or_create_profile(user_id)
        obj = await self.repo.add_sub_entity(model, profile.id, data)
        profile.completeness_score = await self._calc_completeness(profile.id)
        await self.db.commit()
        return obj

    async def update_sub_entity(self, user_id: uuid.UUID, resource: str, entity_id: uuid.UUID, data: dict[str, Any]):
        model = self._model_of(resource)
        profile = await self.get_or_create_profile(user_id)
        obj = await self.repo.update_sub_entity(model, entity_id, profile.id, data)
        if obj is None:
            raise NotFoundException("记录不存在")
        await self.db.commit()
        return obj

    async def delete_sub_entity(self, user_id: uuid.UUID, resource: str, entity_id: uuid.UUID) -> None:
        model = self._model_of(resource)
        profile = await self.get_or_create_profile(user_id)
        ok = await self.repo.delete_sub_entity(model, entity_id, profile.id)
        if not ok:
            raise NotFoundException("记录不存在")
        profile.completeness_score = await self._calc_completeness(profile.id)
        await self.db.commit()

    # ---------- 完整性评分 ----------
    async def _calc_completeness(self, profile_id: uuid.UUID) -> int:
        full = await self.repo.get_full_by_user_id(
            (await self.db.get(Profile, profile_id)).user_id
        )
        score = 0
        if full.name and full.phone and full.email:
            score += 20
        score += min(len(full.educations), 1) * 15
        score += min(len(full.work_experiences), 2) * 15
        score += min(len(full.projects), 2) * 15
        score += min(len(full.skills), 5) * 3
        score += min(len(full.certifications), 2) * 5
        if full.summary:
            score += 10
        return min(score, 100)

    @staticmethod
    def _model_of(resource: str):
        model = SUB_ENTITY_MODELS.get(resource)
        if model is None:
            raise NotFoundException(f"未知的档案子资源: {resource}")
        return model

    # ---------- 自定义信息块（块 → 条目两级） ----------
    def _block_repo(self) -> ProfileBlockRepository:
        return ProfileBlockRepository(self.db)

    async def list_blocks(self, user_id: uuid.UUID) -> list[ProfileBlock]:
        profile = await self.get_or_create_profile(user_id)
        return await self._block_repo().list_by_profile(profile.id)

    async def create_block(self, user_id: uuid.UUID, name: str, fields: list[dict[str, Any]]) -> ProfileBlock:
        profile = await self.get_or_create_profile(user_id)
        block = await self._block_repo().create({
            "profile_id": profile.id, "name": name, "fields": fields,
        })
        await self.db.commit()
        return block

    async def _get_owned_block(self, user_id: uuid.UUID, block_id: uuid.UUID) -> ProfileBlock:
        profile = await self.get_or_create_profile(user_id)
        block = await self._block_repo().get_owned(block_id, profile.id)
        if block is None:
            raise NotFoundException("信息块不存在")
        return block

    async def update_block(
        self, user_id: uuid.UUID, block_id: uuid.UUID,
        name: str | None, fields: list[dict[str, Any]] | None,
    ) -> ProfileBlock:
        block = await self._get_owned_block(user_id, block_id)
        updates: dict[str, Any] = {}
        if name is not None:
            updates["name"] = name
        if fields is not None:
            updates["fields"] = fields
        if updates:
            await self._block_repo().update(block, updates)
        await self.db.commit()
        await self.db.refresh(block)
        return block

    async def delete_block(self, user_id: uuid.UUID, block_id: uuid.UUID) -> None:
        block = await self._get_owned_block(user_id, block_id)
        await self._block_repo().delete(block)  # 条目随级联删除
        await self.db.commit()

    def _validate_entry_data(self, block: ProfileBlock, data: dict[str, Any]) -> dict[str, Any]:
        """条目字段名必须在块的字段定义内；缺失字段补空。"""
        defined = {f.get("name"): f for f in (block.fields or [])}
        unknown = set(data) - set(defined)
        if unknown:
            raise BadRequestException(f"未知字段: {', '.join(sorted(unknown))}")
        return {name: data.get(name) for name in defined}

    async def add_entry(self, user_id: uuid.UUID, block_id: uuid.UUID, data: dict[str, Any]):
        block = await self._get_owned_block(user_id, block_id)
        entry = await self._block_repo().add_entry(block.id, self._validate_entry_data(block, data))
        await self.db.commit()
        return entry

    async def update_entry(self, user_id: uuid.UUID, block_id: uuid.UUID, entry_id: uuid.UUID, data: dict[str, Any]):
        block = await self._get_owned_block(user_id, block_id)
        entry = await self._block_repo().update_entry(entry_id, block.id, self._validate_entry_data(block, data))
        if entry is None:
            raise NotFoundException("记录不存在")
        await self.db.commit()
        return entry

    async def delete_entry(self, user_id: uuid.UUID, block_id: uuid.UUID, entry_id: uuid.UUID) -> None:
        block = await self._get_owned_block(user_id, block_id)
        ok = await self._block_repo().delete_entry(entry_id, block.id)
        if not ok:
            raise NotFoundException("记录不存在")
        await self.db.commit()

    # ---------- 自定义字段定义（各版块随时加字段） ----------
    def _field_def_repo(self) -> CustomFieldDefRepository:
        return CustomFieldDefRepository(self.db)

    async def list_field_defs(self, user_id: uuid.UUID) -> list[CustomFieldDef]:
        profile = await self.get_or_create_profile(user_id)
        return await self._field_def_repo().list_by_profile(profile.id)

    async def create_field_def(
        self, user_id: uuid.UUID, section: str, name: str, label: str, ftype: str,
    ) -> CustomFieldDef:
        if section not in SECTIONS:
            raise BadRequestException(f"未知版块: {section}")
        if name in FIXED_FIELDS[section]:
            raise BadRequestException(f"字段名 {name} 与固定字段冲突")
        profile = await self.get_or_create_profile(user_id)
        repo = self._field_def_repo()
        if await repo.exists(profile.id, section, name):
            raise BadRequestException(f"该版块已存在字段: {name}")
        field_def = await repo.create({
            "profile_id": profile.id, "section": section,
            "name": name, "label": label or name, "type": ftype,
        })
        await self.db.commit()
        return field_def

    async def update_field_def(
        self, user_id: uuid.UUID, def_id: uuid.UUID,
        label: str | None, ftype: str | None,
    ) -> CustomFieldDef:
        """修改字段显示名/类型（字段名为存储 key，不可改）。"""
        profile = await self.get_or_create_profile(user_id)
        field_def = await self._field_def_repo().get_owned(def_id, profile.id)
        if field_def is None:
            raise NotFoundException("字段定义不存在")
        updates: dict[str, Any] = {}
        if label is not None:
            updates["label"] = label
        if ftype is not None:
            updates["type"] = ftype
        if updates:
            await self._field_def_repo().update(field_def, updates)
        await self.db.commit()
        await self.db.refresh(field_def)
        return field_def

    async def delete_field_def(self, user_id: uuid.UUID, def_id: uuid.UUID) -> None:
        """删除字段定义；记录中已存的值保留在 JSON 里，仅不再展示。"""
        profile = await self.get_or_create_profile(user_id)
        field_def = await self._field_def_repo().get_owned(def_id, profile.id)
        if field_def is None:
            raise NotFoundException("字段定义不存在")
        await self._field_def_repo().delete(field_def)
        await self.db.commit()

    # ---------- 供 AI 使用的档案 dict ----------
    async def profile_to_dict(self, user_id: uuid.UUID) -> dict[str, Any]:
        full = await self.get_full_profile(user_id)
        def dump(items, fields):
            out = []
            for i in items:
                if not getattr(i, "visibility", True):
                    continue
                row = {f: getattr(i, f) for f in fields}
                row.update(getattr(i, "custom_fields", None) or {})  # 自定义字段并入（已保证不与固定字段重名）
                out.append(row)
            return out
        profiles = {
            "name": full.name, "gender": full.gender,
            "birth_date": str(full.birth_date or ""), "phone": full.phone,
            "email": full.email, "location": full.location,
            "political_status": full.political_status, "summary": full.summary,
        }
        profiles.update(full.custom_fields or {})
        return {
            "profiles": profiles,
            "educations": dump(full.educations, ["school", "major", "degree", "start_date", "end_date", "gpa", "courses", "is_current"]),
            "work_experiences": dump(full.work_experiences, ["company", "position", "start_date", "end_date", "description", "achievements", "is_current"]),
            "projects": dump(full.projects, ["name", "role", "tech_stack", "start_date", "end_date", "description", "highlights", "url"]),
            "skills": dump(full.skills, ["name", "category", "proficiency"]),
            "certifications": dump(full.certifications, ["name", "issuer", "issue_date", "expiry_date", "credential_id"]),
            "family_members": dump(full.family_members, ["name", "relationship", "work_unit", "position", "phone"]),
            "custom_blocks": [
                {
                    "name": b.name,
                    "entries": [
                        {(f.get("label") or f.get("name")): e.data.get(f.get("name"))
                         for f in (b.fields or [])}
                        for e in b.entries
                    ],
                }
                for b in full.custom_blocks
            ],
        }
