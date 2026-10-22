"""报名表业务层：上传 → 解析 → AI 映射 → 填充 → 下载。"""
from __future__ import annotations  # 类内有方法名 list，注解延迟求值避免遮蔽内置类型
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.form import FormModel
from app.repositories.form_repo import FormRepository
from app.services.ai_service import AIService
from app.services.config_service import ConfigService
from app.services.form_filler import form_filler
from app.services.form_parser import form_parser
from app.services.profile_service import ProfileService
from app.utils.exceptions import BadRequestException, NotFoundException
from app.utils.file_handler import save_upload_file


class FormService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = FormRepository(db)

    async def _ai(self) -> AIService:
        """按运行时配置（system_config）构造 AI 客户端，未配置时回退 .env。"""
        return AIService(await ConfigService(self.db).get_effective_kimi_config())

    # ---------------- 上传 ----------------
    async def upload(self, user_id: uuid.UUID, filename: str, data: bytes) -> FormModel:
        file_path, file_type = await save_upload_file(data, filename)
        form = await self.repo.create({
            "user_id": user_id, "original_filename": filename,
            "file_path": file_path, "file_type": file_type, "status": "uploaded",
        })
        await self.db.commit()
        return form

    async def get(self, form_id: uuid.UUID, user_id: uuid.UUID) -> FormModel:
        form = await self.repo.get_by_user(form_id, user_id)
        if form is None:
            raise NotFoundException("报名表不存在")
        return form

    async def list(self, user_id: uuid.UUID, offset: int = 0, limit: int = 50) -> list[FormModel]:
        return await self.repo.list_by_user(user_id, offset, limit)

    async def delete(self, form_id: uuid.UUID, user_id: uuid.UUID) -> None:
        form = await self.get(form_id, user_id)
        await self.repo.delete(form)
        await self.db.commit()

    # ---------------- 解析 ----------------
    async def analyze(self, form_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any]:
        form = await self.get(form_id, user_id)
        structure = form_parser.parse(form.file_path, form.file_type)
        await self.repo.update(form, {"form_structure": structure.model_dump(), "status": "analyzed"})
        await self.db.commit()
        return structure.model_dump()

    # ---------------- AI 映射（可人工覆盖） ----------------
    async def build_mapping(
        self, form_id: uuid.UUID, user_id: uuid.UUID,
        manual_mappings: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        form = await self.get(form_id, user_id)
        if not form.form_structure:
            raise BadRequestException("请先调用 analysis 接口完成表单解析")

        if manual_mappings is None:
            profile_dict = await ProfileService(self.db).profile_to_dict(user_id)
            ai = await self._ai()
            result = await ai.map_form_fields(form.form_structure.get("fields", []), profile_dict)
        else:
            result = {"mappings": manual_mappings, "unmapped": [], "needs_review": []}

        await self.repo.update(form, {"field_mapping": result, "status": "mapped"})
        await self.db.commit()
        return result

    # ---------------- 填充 ----------------
    async def fill(self, form_id: uuid.UUID, user_id: uuid.UUID) -> tuple[str, dict[str, Any]]:
        form = await self.get(form_id, user_id)
        if not form.field_mapping:
            raise BadRequestException("请先调用 mapping 接口完成字段映射")

        mapping_data = {
            m["form_field"]: m.get("value")
            for m in form.field_mapping.get("mappings", [])
            if m.get("value")
        }
        if not mapping_data:
            raise BadRequestException("映射结果中没有可填充的值")

        ext = Path(form.original_filename).suffix
        output_path = str(Path(settings.EXPORT_DIR) / f"{Path(form.original_filename).stem}_已填写{ext}")
        filled_path = form_filler.fill(form.file_type, form.file_path, mapping_data, output_path)

        await self.repo.update(form, {"filled_data": mapping_data, "status": "filled"})
        await self.db.commit()
        return filled_path, mapping_data

    # ---------------- 下载 ----------------
    async def get_download_path(self, form_id: uuid.UUID, user_id: uuid.UUID) -> str:
        form = await self.get(form_id, user_id)
        if form.status != "filled":
            raise BadRequestException("报名表尚未填充完成")
        ext = Path(form.original_filename).suffix
        path = Path(settings.EXPORT_DIR) / f"{Path(form.original_filename).stem}_已填写{ext}"
        if not path.exists():
            # 非表单 PDF 的填写指南
            guide = path.with_suffix(".填写指南.txt")
            if guide.exists():
                return str(guide)
            raise NotFoundException("填充文件不存在，请重新执行 fill")
        return str(path)
