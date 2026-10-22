"""投递管理业务层：CRUD + 筛选列表 + 统计 + 跟进（指令 8）+ 投递版本锁定。"""
from __future__ import annotations  # 类内有方法名 list，注解延迟求值避免遮蔽内置类型

import asyncio
import logging
import shutil
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.application import Application
from app.repositories.application_repo import ApplicationRepository
from app.repositories.jd_repo import JDRepository
from app.repositories.resume_repo import ResumeRepository
from app.schemas.application import ApplicationCreate, ApplicationUpdate
from app.utils.exceptions import BadRequestException, NotFoundException

logger = logging.getLogger("application_service")


class ApplicationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ApplicationRepository(db)

    async def _attach_related(self, items: list[Application]) -> list[Application]:
        """附带关联简历版本名与 JD 信息（列表展示用）。"""
        resume_repo, jd_repo = ResumeRepository(self.db), JDRepository(self.db)
        for item in items:
            if item.resume_id:
                resume = await resume_repo.get(item.resume_id)
                item.resume_version_name = resume.version_name if resume else None
            if item.jd_id:
                jd = await jd_repo.get(item.jd_id)
                item.jd_company = jd.company_name if jd else None
                item.jd_position = jd.position_title if jd else None
            # 派生标记：pydantic from_attributes 直接读这两个动态属性
            item.has_snapshot = item.resume_snapshot is not None
            item.has_snapshot_pdf = bool(item.snapshot_pdf_path)
        return items

    async def _build_snapshot(self, user_id: uuid.UUID, resume_id: uuid.UUID | None, jd_id: uuid.UUID | None) -> dict[str, Any]:
        """投递时锁定招聘方实际看到的版本：简历内容、模板、PDF 副本、匹配分、JD 原文。

        没有关联简历时返回空 dict（纯手工记录也允许）。PDF 复制到独立子目录，
        防止用户后续重新导出覆盖原文件 —— 回看时看到的必须是投递当时那份。
        """
        snapshot: dict[str, Any] = {}
        if resume_id:
            resume = await ResumeRepository(self.db).get(resume_id)
            if resume is None or resume.user_id != user_id:
                raise BadRequestException("关联的简历不存在")
            if resume.status not in {"generated", "exported"}:
                raise BadRequestException("只能关联已生成成功的简历")
            from app.services.resume_service import exportable_resume_data
            snapshot["resume_snapshot"] = exportable_resume_data(resume.resume_data)
            snapshot["snapshot_template"] = resume.html_template
            snapshot["snapshot_match_score"] = resume.match_score
            if not jd_id:
                jd_id = resume.jd_id
            if resume.pdf_path and Path(resume.pdf_path).exists():
                app_dir = Path(settings.EXPORT_DIR) / "applications"
                app_dir.mkdir(parents=True, exist_ok=True)
                copy_path = app_dir / f"{uuid.uuid4().hex}.pdf"
                await asyncio.to_thread(shutil.copy2, resume.pdf_path, copy_path)
                snapshot["snapshot_pdf_path"] = str(copy_path)
                logger.info("[投递快照] resume=%s PDF 已复制副本 %s", resume_id, copy_path)
        if jd_id:
            jd = await JDRepository(self.db).get(jd_id)
            if jd is not None and jd.user_id == user_id:
                snapshot["jd_snapshot"] = {
                    "company_name": jd.company_name,
                    "position_title": jd.position_title,
                    "raw_text": jd.raw_text,
                    "parsed_data": jd.parsed_data,
                }
                snapshot.setdefault("jd_id", jd_id)
        return snapshot

    async def create(self, user_id: uuid.UUID, data: ApplicationCreate) -> Application:
        payload = {"user_id": user_id, **data.model_dump()}
        snapshot = await self._build_snapshot(user_id, data.resume_id, data.jd_id)
        payload.update(snapshot)
        app = await self.repo.create(payload)
        await self.db.commit()
        app.has_snapshot = app.resume_snapshot is not None
        app.has_snapshot_pdf = bool(app.snapshot_pdf_path)
        return app

    async def get_snapshot(self, app_id: uuid.UUID, user_id: uuid.UUID) -> Application:
        app = await self.get(app_id, user_id)
        if app.resume_snapshot is None:
            raise NotFoundException("该投递记录没有版本快照（旧记录或投递时未关联简历）")
        await self._attach_related([app])
        app.has_snapshot_pdf = bool(app.snapshot_pdf_path and Path(app.snapshot_pdf_path).exists())
        return app

    async def snapshot_pdf_path(self, app_id: uuid.UUID, user_id: uuid.UUID) -> str:
        app = await self.get(app_id, user_id)
        if not app.snapshot_pdf_path or not Path(app.snapshot_pdf_path).exists():
            raise NotFoundException("该投递记录没有可用的 PDF 快照（投递时简历未导出 PDF）")
        return app.snapshot_pdf_path

    async def get(self, app_id: uuid.UUID, user_id: uuid.UUID) -> Application:
        app = await self.repo.get_by_user(app_id, user_id)
        if app is None:
            raise NotFoundException("投递记录不存在")
        return app

    async def list(
        self, user_id: uuid.UUID, status: str | None = None, channel: str | None = None,
        date_from: date | None = None, date_to: date | None = None,
        offset: int = 0, limit: int = 50,
    ) -> tuple[int, list[Application]]:
        total, items = await self.repo.list_by_user(user_id, status, channel, date_from, date_to, offset, limit)
        return total, await self._attach_related(items)

    async def update(self, app_id: uuid.UUID, user_id: uuid.UUID, data: ApplicationUpdate) -> Application:
        app = await self.get(app_id, user_id)
        await self.repo.update(app, data.model_dump(exclude_unset=True))
        await self.db.commit()
        return app

    async def delete(self, app_id: uuid.UUID, user_id: uuid.UUID) -> None:
        app = await self.get(app_id, user_id)
        await self.repo.delete(app)
        await self.db.commit()

    async def stats(self, user_id: uuid.UUID) -> dict[str, Any]:
        by_status = await self.repo.count_group_by(user_id, Application.status)
        by_channel = await self.repo.count_group_by(user_id, Application.channel)
        total = sum(by_status.values())
        converted = by_status.get("interview", 0) + by_status.get("offer", 0)
        per_day = await self.repo.count_by_day(user_id, 30)
        # 零填充：前端趋势图需要连续 30 天的横轴，没有投递的天也要补 0
        today = date.today()
        trend_30d = [
            {"date": (today - timedelta(days=29 - i)).isoformat(), "count": 0}
            for i in range(30)
        ]
        for point in trend_30d:
            point["count"] = per_day.get(point["date"], 0)
        return {
            "total": total,
            "by_status": by_status,
            "by_channel": by_channel,
            "conversion_rate": round(converted / total * 100, 1) if total else 0.0,
            "recent_7_days": await self.repo.count_recent(user_id, 7),
            "trend_30d": trend_30d,
        }

    async def follow_ups(self, user_id: uuid.UUID) -> list[Application]:
        return await self._attach_related(await self.repo.list_follow_ups(user_id))
