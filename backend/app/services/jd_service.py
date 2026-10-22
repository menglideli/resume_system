"""JD 解析业务层：AI 解析 + 入库 + 匹配预览。"""
from __future__ import annotations  # 类内有方法名 list，注解延迟求值避免遮蔽内置类型
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_description import JobDescription
from app.repositories.jd_repo import JDRepository
from app.services.ai_service import AIService
from app.services.config_service import ConfigService
from app.services.profile_service import ProfileService
from app.utils.exceptions import NotFoundException


class JDService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = JDRepository(db)

    async def _ai(self) -> AIService:
        """按运行时配置（system_config）构造 AI 客户端，未配置时回退 .env。"""
        return AIService(await ConfigService(self.db).get_effective_kimi_config())

    async def parse_and_save(
        self, user_id: uuid.UUID, raw_text: str,
        company_name: str | None, position_title: str | None,
    ) -> tuple[JobDescription, dict[str, int]]:
        # ---- 1) AI 解析 ----
        ai = await self._ai()
        parsed = await ai.parse_jd(raw_text)
        company = company_name or parsed.get("company")
        position = position_title or parsed.get("position")

        # ---- 2) 入库 ----
        jd = await self.repo.create({
            "user_id": user_id, "company_name": company,
            "position_title": position, "raw_text": raw_text, "parsed_data": parsed,
        })

        # ---- 3) 匹配预览：档案完整度 + 关键词重叠估算 ----
        profile_svc = ProfileService(self.db)
        profile = await profile_svc.get_or_create_profile(user_id)
        estimated = self._estimate_match(await profile_svc.profile_to_dict(user_id), parsed)
        await self.db.commit()
        return jd, {"profile_completeness": profile.completeness_score, "estimated_match": estimated}

    @staticmethod
    def _estimate_match(profile_dict: dict[str, Any], parsed: dict[str, Any]) -> int:
        profile_text = str(profile_dict).lower()
        keywords = (parsed.get("keywords") or []) + (parsed.get("ats_keywords") or [])
        if not keywords:
            return 60
        hit = sum(1 for k in keywords if str(k).lower() in profile_text)
        return min(95, 40 + int(55 * hit / len(keywords)))

    async def get(self, jd_id: uuid.UUID, user_id: uuid.UUID) -> JobDescription:
        jd = await self.repo.get(jd_id)
        if jd is None or jd.user_id != user_id:
            raise NotFoundException("JD 不存在")
        return jd

    async def list(self, user_id: uuid.UUID, offset: int = 0, limit: int = 50) -> list[JobDescription]:
        return await self.repo.list_by_user(user_id, offset, limit)

    async def delete(self, jd_id: uuid.UUID, user_id: uuid.UUID) -> None:
        jd = await self.get(jd_id, user_id)
        await self.repo.delete(jd)
        await self.db.commit()
