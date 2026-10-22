"""简历业务层：定制生成（后台任务）、查询、删除、PDF 导出、诊断、面试 Q&A。"""
from __future__ import annotations  # 类内有方法名 list，注解延迟求值避免遮蔽内置类型
import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.resume import Resume
from app.models.work import WorkExperience
from app.repositories.jd_repo import JDRepository
from app.repositories.profile_repo import ProfileRepository
from app.repositories.resume_repo import ResumeRepository
from app.repositories.resume_version_repo import ResumeVersionRepository
from app.services.ai_service import AIService
from app.services.config_service import ConfigService
from app.services.profile_service import ProfileService
from app.services.resume_renderer import resume_renderer, version_name_to_filename
from app.utils.exceptions import BadRequestException, NotFoundException
from app.utils.file_handler import ensure_export_path

logger = logging.getLogger("resume_service")

# 后台生成任务引用集：防止 asyncio.Task 被垃圾回收提前回收导致任务丢失
_BG_TASKS: set[asyncio.Task] = set()

# 当前进程内真正在跑的生成任务：resume_id(str) → 启动时间戳。
# uvicorn --reload / 进程重启会直接杀掉子进程，任务凭空消失但数据库里仍是 pending，
# 巡检协程据此判断“孤儿 pending”并置为失败，避免前端永远显示“生成中”。
_RUNNING: dict[str, float] = {}

GEN_TIMEOUT = 900       # 单个生成任务的总超时（秒），与推理模型 600s 单次上限匹配
STALE_AFTER = 600       # pending 超过该秒数且本进程无对应运行中任务 → 判定为孤儿
WATCHDOG_INTERVAL = 60  # 巡检周期（秒）


def _as_local_naive(dt: datetime | None) -> datetime | None:
    """MySQL DATETIME 取回来可能是 naive（本地时间），统一成本地 naive 再做比较。"""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone().replace(tzinfo=None)
    return dt


# 档案里真正能撑起一份简历的清单型字段
_PROFILE_LIST_KEYS = ("educations", "work_experiences", "projects", "skills", "certifications", "custom_blocks")
# 这些只要有任意一个非空，就说明用户至少填过东西
_PROFILE_CORE_KEYS = ("name", "summary", "phone", "email", "location")


def is_profile_empty(profile_dict: dict[str, Any]) -> bool:
    """档案是否实质为空。

    空档案照样能跑完一次推理（约 4 分钟），但产出必然是没有 sections 的空壳，
    状态还写成 generated —— 用户看到「生成成功」点进去却是一片空白。
    与其烧完 token 再给个假成功，不如在调用 AI 之前就快速失败。
    """
    if any(profile_dict.get(k) for k in _PROFILE_LIST_KEYS):
        return False
    profiles = profile_dict.get("profiles") or {}
    return not any(str(profiles.get(k) or "").strip() for k in _PROFILE_CORE_KEYS)


MAX_ENHANCEMENTS = 4
_RISK_LEVELS = ("high", "medium", "low")


def sanitize_enhancements(raw: Any) -> list[dict[str, Any]]:
    """清洗待确认的工作经历 bullet 建议，并兼容模型偶发返回的旧 project 结构。"""
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        raw_bullets = item.get("suggested_bullets")
        legacy_project = item.get("project") if isinstance(item.get("project"), dict) else None
        if not isinstance(raw_bullets, list) and legacy_project is not None:
            raw_bullets = legacy_project.get("bullets")
        bullets = [
            str(b).strip()[:500] for b in raw_bullets
            if b is not None and str(b).strip()
        ] if isinstance(raw_bullets, list) else []
        if not bullets:
            continue
        target_ref = str(item.get("target_source_ref") or "").strip()
        if target_ref and not (target_ref.startswith("work_experiences[") and target_ref.endswith("]")):
            target_ref = ""
        risk = item.get("risk")
        out.append({
            "gap": str(item.get("gap") or "")[:300],
            "basis": str(item.get("basis") or "")[:300],
            "risk": risk if risk in _RISK_LEVELS else "medium",
            "target_source_ref": target_ref,
            "suggested_bullets": bullets[:6],
            "legacy": legacy_project is not None,
        })
    return out[:MAX_ENHANCEMENTS]


_SECTION_SOURCES = {
    "skills": ("skills", "name"),
    "experience": ("work_experiences", "company"),
    "projects": ("projects", "name"),
    "education": ("educations", "school"),
    "certifications": ("certifications", "name"),
}


def sanitize_resume_facts(raw: Any, profile: dict[str, Any]) -> dict[str, Any]:
    """保留可回指档案的正式简历条目，阻断 AI 凭空新增实体。

    文案和 bullet 可以由模型改写；公司、学校、项目、技能、证书等身份字段
    必须通过 source_ref 或名称与档案对应。旧模型未返回 source_ref 时允许按名称
    回填，避免合法条目被误删。
    """
    if not isinstance(raw, dict):
        return {}
    data = dict(raw)
    clean_sections: list[dict[str, Any]] = []
    for section in data.get("sections") or []:
        if not isinstance(section, dict):
            continue
        clean = dict(section)
        source_spec = _SECTION_SOURCES.get(str(clean.get("type") or ""))
        if source_spec is None:
            if clean.get("type") == "summary" and str(clean.get("content") or "").strip():
                clean_sections.append(clean)
            continue
        source_key, identity_key = source_spec
        sources = profile.get(source_key) or []
        kept: list[dict[str, Any]] = []
        for item in clean.get("items") or []:
            if not isinstance(item, dict):
                continue
            match_index: int | None = None
            source_ref = str(item.get("source_ref") or "")
            prefix = f"{source_key}["
            if source_ref.startswith(prefix) and source_ref.endswith("]"):
                try:
                    idx = int(source_ref[len(prefix):-1])
                    if 0 <= idx < len(sources):
                        match_index = idx
                except ValueError:
                    pass
            if match_index is None:
                identity = str(item.get(identity_key) or "").strip().casefold()
                match_index = next(
                    (i for i, source in enumerate(sources)
                     if identity and str(source.get(identity_key) or "").strip().casefold() == identity),
                    None,
                )
            if match_index is None:
                continue
            verified = dict(item)
            source = sources[match_index]
            # source_ref 只能证明“指向某条档案”，不能允许模型把该条的身份字段改名。
            # 实体名始终恢复档案原值，AI 只负责排序和文案改写。
            verified[identity_key] = source.get(identity_key)
            verified["source_ref"] = f"{source_key}[{match_index}]"
            if source_key == "skills":
                verified["category"] = str(source.get("category") or "其他技能")
                proficiency = source.get("proficiency")
                if proficiency is not None:
                    verified["level"] = {5: "精通", 4: "熟练", 3: "掌握", 2: "了解", 1: "入门"}.get(
                        int(proficiency), ""
                    )
            kept.append(verified)
        if kept:
            clean["items"] = sorted(kept, key=lambda x: x.get("relevance") or 0, reverse=True)
            clean_sections.append(clean)
    data["sections"] = clean_sections
    return data


def validate_resume_content_budget(resume_data: dict[str, Any], profile: dict[str, Any]) -> None:
    """档案素材充足时拒绝明显过短的结果；素材不足时不诱导模型编造。"""
    source_items = (profile.get("work_experiences") or []) + (profile.get("projects") or [])
    source_text = " ".join(
        str(value or "")
        for item in source_items
        for key in ("description", "achievements", "highlights")
        for value in ([item.get(key)] if not isinstance(item.get(key), list) else item.get(key))
    )
    if len(source_items) < 2 or len(source_text.strip()) < 300:
        return
    sections = resume_data.get("sections") or []
    summary = next((str(s.get("content") or "") for s in sections if s.get("type") == "summary"), "")
    career_items = [
        item for section in sections if section.get("type") in {"experience", "projects"}
        for item in (section.get("items") or [])
    ]
    bullet_count = sum(len(item.get("bullets") or []) for item in career_items)
    if len(summary.strip()) < 80 or len(career_items) < 2 or bullet_count < 5:
        raise BadRequestException(
            "AI 返回的简历内容过短，未充分使用档案中的工作/项目素材。"
            "请重试生成；若仍失败，请检查档案描述是否完整"
        )


def sanitize_match_details(raw: Any, profile: dict[str, Any]) -> list[dict[str, Any]]:
    """只保留能够回指真实档案的 JD 覆盖证据；missing 项可无证据。"""
    source_keys = {source_key for source_key, _ in _SECTION_SOURCES.values()}
    valid_refs = {
        f"{source_key}[{index}]"
        for source_key in source_keys
        for index, _ in enumerate(profile.get(source_key) or [])
    }
    if not isinstance(raw, list):
        return []
    clean: list[dict[str, Any]] = []
    for item in raw[:30]:
        if not isinstance(item, dict) or not str(item.get("requirement") or "").strip():
            continue
        status = item.get("status") if item.get("status") in {"direct", "adjacent", "missing"} else "missing"
        refs = [ref for ref in (item.get("evidence_refs") or []) if ref in valid_refs]
        if status != "missing" and not refs:
            status = "missing"
        clean.append({
            "requirement": str(item["requirement"]).strip()[:300],
            "priority": item.get("priority") if item.get("priority") in {"must", "core", "bonus"} else "core",
            "status": status,
            "evidence_refs": refs,
            "resume_usage": str(item.get("resume_usage") or "")[:300],
        })
    return clean


def match_score_from_details(details: list[dict[str, Any]]) -> int | None:
    if not details:
        return None
    weights = {"must": 5, "core": 4, "bonus": 2}
    factors = {"direct": 1.0, "adjacent": 0.5, "missing": 0.0}
    total = sum(weights[item["priority"]] for item in details)
    earned = sum(weights[item["priority"]] * factors[item["status"]] for item in details)
    return round(earned / total * 100) if total else 0


def exportable_resume_data(raw: Any) -> dict[str, Any]:
    """导出前移除未确认的 AI 补充；确认过的条目才属于正式内容。"""
    data = dict(raw or {})
    sections: list[dict[str, Any]] = []
    for section in data.get("sections") or []:
        clean = dict(section)
        clean_items: list[Any] = []
        for item in clean.get("items") or []:
            # 编辑器里「隐藏」的条目不进导出：隐藏 ≠ 删除，档案事实与版本历史都还在
            if isinstance(item, dict) and item.get("hidden"):
                continue
            if (isinstance(item, dict)
                    and item.get("provenance") == "user_confirmed_enhancement"):
                if item.get("verified") is not True:
                    continue
                normalized = dict(item)
                if not normalized.get("relevance"):
                    risk = (normalized.get("enhancement_context") or {}).get("risk")
                    normalized["relevance"] = {"high": 10, "medium": 8, "low": 7}.get(risk, 8)
                clean_items.append(normalized)
            else:
                clean_items.append(item)
        clean["items"] = clean_items
        sections.append(clean)
    data["sections"] = sections
    return data


# ---------------- 编辑器：结构校验与统计（纯函数，不调 AI） ----------------

MAX_VERSIONS = 50          # 每份简历保留的版本快照上限，超出删最旧
_CHARS_PER_PAGE = 900      # 预计页数启发式：A4 正常密度约 900 个非空白字符/页

# 上限值：编辑器提交的是用户自己的内容，不做事实校验，但要挡住畸形/超大 payload
_EDIT_LIMITS = {
    "sections": 12, "items": 50, "bullets": 30,
    "bullet_len": 1000, "text_len": 2000, "summary_len": 5000, "tech_stack": 30,
}
_HEADER_STR_KEYS = ("name", "title", "avatar_url")
_CONTACT_STR_KEYS = ("phone", "email", "location")


def _clip(value: Any, limit: int) -> str:
    return str(value or "")[:limit]


def sanitize_user_edits(raw: Any) -> dict[str, Any]:
    """校验并规范化编辑器提交的 resume_data。

    与 sanitize_resume_facts 的边界不同：那边防 AI 编造实体，这边内容以用户输入为准，
    只管结构形状和体量上限（防止畸形 JSON 把渲染器/前端打挂）。
    match_details 不在这里处理 —— 匹配证据由服务端从库里原样保留，不接受前端改写。
    """
    if not isinstance(raw, dict):
        raise BadRequestException("简历数据必须是 JSON 对象")
    sections_raw = raw.get("sections")
    if not isinstance(sections_raw, list) or not sections_raw:
        raise BadRequestException("简历至少要包含一个内容模块")
    if len(sections_raw) > _EDIT_LIMITS["sections"]:
        raise BadRequestException(f"内容模块数量超过上限（{_EDIT_LIMITS['sections']}）")

    out: dict[str, Any] = {}
    header = raw.get("header")
    if isinstance(header, dict):
        clean_header: dict[str, Any] = {k: _clip(header.get(k), 200) for k in _HEADER_STR_KEYS}
        contact = header.get("contact")
        if isinstance(contact, dict):
            clean_header["contact"] = {k: _clip(contact.get(k), 200) for k in _CONTACT_STR_KEYS}
        out["header"] = clean_header

    clean_sections: list[dict[str, Any]] = []
    for section in sections_raw:
        if not isinstance(section, dict):
            raise BadRequestException("内容模块必须是对象")
        sec = dict(section)
        sec_type = str(sec.get("type") or "")
        if sec_type == "summary":
            sec["content"] = _clip(sec.get("content"), _EDIT_LIMITS["summary_len"])
            clean_sections.append(sec)
            continue
        items_raw = sec.get("items")
        if not isinstance(items_raw, list):
            raise BadRequestException(f"内容模块（{sec_type or '未知类型'}）的 items 必须是数组")
        if len(items_raw) > _EDIT_LIMITS["items"]:
            raise BadRequestException(f"单个模块条目数超过上限（{_EDIT_LIMITS['items']}）")
        clean_items: list[dict[str, Any]] = []
        for item in items_raw:
            if not isinstance(item, dict):
                raise BadRequestException("条目必须是对象")
            clean_item = {
                key: (value[:_EDIT_LIMITS["text_len"]] if isinstance(value, str) else value)
                for key, value in item.items()
            }
            bullets = clean_item.get("bullets")
            if bullets is not None:
                if not isinstance(bullets, list):
                    raise BadRequestException("bullets 必须是数组")
                clean_item["bullets"] = [
                    _clip(b, _EDIT_LIMITS["bullet_len"])
                    for b in bullets[:_EDIT_LIMITS["bullets"]] if str(b or "").strip()
                ]
            tech_stack = clean_item.get("tech_stack")
            if isinstance(tech_stack, list):
                clean_item["tech_stack"] = [
                    _clip(t, 100) for t in tech_stack[:_EDIT_LIMITS["tech_stack"]]
                ]
            relevance = clean_item.get("relevance")
            if relevance is not None:
                try:
                    clean_item["relevance"] = max(0, min(10, int(relevance)))
                except (TypeError, ValueError):
                    clean_item.pop("relevance", None)
            if "hidden" in clean_item:
                clean_item["hidden"] = bool(clean_item["hidden"])
            clean_items.append(clean_item)
        sec["items"] = clean_items
        clean_sections.append(sec)
    out["sections"] = clean_sections
    return out


def collect_visible_text(resume_data: dict[str, Any]) -> str:
    """拼接简历中所有可见文本（隐藏条目不计），供字数统计与关键词覆盖计算。"""
    parts: list[str] = []
    header = resume_data.get("header") or {}
    if isinstance(header, dict):
        parts.append(str(header.get("title") or ""))
    for section in resume_data.get("sections") or []:
        if not isinstance(section, dict):
            continue
        if section.get("type") == "summary":
            parts.append(str(section.get("content") or ""))
            continue
        for item in section.get("items") or []:
            if not isinstance(item, dict) or item.get("hidden"):
                continue
            for key in ("company", "position", "period", "name", "role",
                        "school", "major", "degree", "issuer", "category", "level"):
                value = item.get(key)
                if isinstance(value, str):
                    parts.append(value)
            for list_key in ("tech_stack", "bullets"):
                value = item.get(list_key)
                if isinstance(value, list):
                    parts.extend(str(v) for v in value)
    return "\n".join(parts)


def resume_stats(resume_data: dict[str, Any], jd_parsed: dict[str, Any] | None = None) -> dict[str, Any]:
    """字数/条目数/预计页数/JD 关键词覆盖 —— 全部确定性计算，不调 AI。"""
    data = resume_data or {}
    text = collect_visible_text(data)
    char_count = len("".join(text.split()))
    item_count = 0
    bullet_count = 0
    for section in data.get("sections") or []:
        if not isinstance(section, dict):
            continue
        for item in section.get("items") or []:
            if not isinstance(item, dict) or item.get("hidden"):
                continue
            item_count += 1
            bullets = item.get("bullets")
            if isinstance(bullets, list):
                bullet_count += len(bullets)
    keywords = [
        str(k).strip()
        for key in ("keywords", "ats_keywords")
        for k in ((jd_parsed or {}).get(key) or [])
        if str(k).strip()
    ]
    lowered = text.lower()
    covered = [k for k in keywords if k.lower() in lowered]
    missing = [k for k in keywords if k.lower() not in lowered]
    return {
        "char_count": char_count,
        "item_count": item_count,
        "bullet_count": bullet_count,
        "estimated_pages": max(1, -(-char_count // _CHARS_PER_PAGE)),
        "keyword_total": len(keywords),
        "keyword_covered": len(covered),
        "keyword_coverage": round(len(covered) / len(keywords) * 100) if keywords else None,
        "missing_keywords": missing[:20],
    }


class ResumeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ResumeRepository(db)
        self.jd_repo = JDRepository(db)
        self.version_repo = ResumeVersionRepository(db)

    async def _ai(self) -> AIService:
        """按运行时配置（system_config）构造 AI 客户端，未配置时回退 .env。"""
        return AIService(await ConfigService(self.db).get_effective_kimi_config())

    # ---------------- 生成（后台任务） ----------------
    async def generate(self, user_id: uuid.UUID, jd_id: uuid.UUID, preferences: dict[str, Any]) -> Resume:
        jd = await self.jd_repo.get(jd_id)
        if jd is None or jd.user_id != user_id:
            raise NotFoundException("JD 不存在，请先解析 JD")
        if not jd.parsed_data:
            raise BadRequestException("该 JD 尚未解析")

        # 提交即返回：先落 pending 记录，AI 生成进后台异步执行
        resume = await self.repo.create({
            "user_id": user_id,
            "jd_id": jd_id,
            "version_name": f"{jd.company_name or '岗位'}_{jd.position_title or '简历'}",
            "resume_data": {},
            "html_template": preferences.get("template") or "technical",
            "preferences": preferences,
            "status": "pending",
        })
        await self.db.commit()

        _RUNNING[str(resume.id)] = time.time()
        task = asyncio.create_task(_run_generation_bg(resume.id, user_id, jd_id, preferences))
        _BG_TASKS.add(task)
        task.add_done_callback(_BG_TASKS.discard)
        logger.info("[生成任务] 已提交 resume=%s user=%s jd=%s 后台任务开始执行", resume.id, user_id, jd_id)
        return resume

    # ---------------- 重试（复用原记录，不新增垃圾行） ----------------
    async def retry(self, resume_id: uuid.UUID, user_id: uuid.UUID) -> Resume:
        """对失败/中断的任务原地重跑：重置状态为 pending 并重新提交后台任务。"""
        resume = await self.repo.get_by_user(resume_id, user_id)
        if resume is None:
            raise NotFoundException("简历不存在")
        if not resume.jd_id:
            raise BadRequestException("该任务未关联 JD，请删除后重新生成")
        running_task = _RUNNING.get(str(resume.id))
        if running_task and time.time() - running_task < GEN_TIMEOUT:
            raise BadRequestException("该任务正在生成中，请耐心等待")
        # 只允许重跑失败/中断的任务。对已成功生成的结果重试纯属浪费一次推理调用，
        # 而且下面的清空一旦误触发就是不可逆的内容丢失。
        if resume.status == "generated":
            raise BadRequestException("该简历已生成成功，无需重试；如需重新生成请先删除再新建")

        # 刻意不清空 resume_data：与面试准备同一策略，生成失败时旧内容还在，
        # 前端 pending 期间显示加载态而不是过期内容，成功后再整体覆盖。
        await self.repo.update(resume, {
            "status": "pending",
            "error_message": None,
        })
        await self.db.commit()

        # 用当初生成时的参数重跑，否则重试出来的模板/页数/语言跟用户选的对不上
        preferences = resume.preferences or {}
        _RUNNING[str(resume.id)] = time.time()
        task = asyncio.create_task(_run_generation_bg(resume.id, user_id, resume.jd_id, preferences))
        _BG_TASKS.add(task)
        task.add_done_callback(_BG_TASKS.discard)
        logger.info("[生成任务] resume=%s 手动重试，后台任务已重新提交（参数 %s）", resume.id, preferences)
        return resume

    # ---------------- 查询 ----------------
    async def get(self, resume_id: uuid.UUID, user_id: uuid.UUID) -> Resume:
        resume = await self.repo.get_by_user(resume_id, user_id)
        if resume is None:
            raise NotFoundException("简历不存在")
        return resume

    async def list(self, user_id: uuid.UUID, offset: int = 0, limit: int = 50) -> list[Resume]:
        return await self.repo.list_by_user(user_id, offset, limit)

    async def delete(self, resume_id: uuid.UUID, user_id: uuid.UUID) -> None:
        resume = await self.get(resume_id, user_id)
        await self.repo.delete(resume)
        await self.db.commit()

    # ---------------- 编辑器 ----------------
    async def update_data(self, resume_id: uuid.UUID, user_id: uuid.UUID, raw_data: Any) -> Resume:
        """保存用户编辑后的简历内容：先拍版本快照，再覆盖当前数据。"""
        resume = await self.get(resume_id, user_id)
        if resume.status not in {"generated", "exported"}:
            raise BadRequestException("只有生成成功的简历才能编辑")
        cleaned = sanitize_user_edits(raw_data)
        existing = resume.resume_data or {}
        # 匹配证据（match_details）由服务端保留，不接受前端改写
        cleaned["match_details"] = existing.get("match_details") or []
        await self._ensure_baseline(resume)
        await self._snapshot(resume, "user_edit", cleaned, resume.match_score)
        await self.repo.update(resume, {
            "resume_data": cleaned,
            "pdf_path": None,          # 内容变了，旧 PDF 作废
            "status": "generated",     # exported 回退，提示需要重新导出
        })
        await self.db.commit()
        logger.info("[编辑] resume=%s 用户保存编辑，版本快照已追加", resume_id)
        return resume

    async def stats(self, resume_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any]:
        resume = await self.get(resume_id, user_id)
        jd_parsed: dict[str, Any] = {}
        if resume.jd_id:
            jd = await self.jd_repo.get(resume.jd_id)
            jd_parsed = (jd.parsed_data if jd else None) or {}
        return resume_stats(resume.resume_data or {}, jd_parsed)

    # ---------------- 版本历史 ----------------
    async def _ensure_baseline(self, resume: Resume) -> None:
        """首次修改前给存量简历补一条基线版本。

        版本功能上线前生成的简历没有任何历史；若只快照修改后的新状态，
        AI 原始版本会在第一次编辑后永久丢失、无法回滚。
        """
        if await self.version_repo.count_by_resume(resume.id) == 0 and (resume.resume_data or {}).get("sections"):
            await self._snapshot(resume, "ai_generated", resume.resume_data, resume.match_score)

    async def _snapshot(self, resume: Resume, label: str, data: dict[str, Any], match_score: int | None) -> None:
        """追加一条版本快照并裁剪超额历史。不 commit，由调用方随业务写入一起提交。

        约定：版本序列记录每一次「落地的内容状态」，当前 resume_data 永远等于最新版本，
        所以回滚无需先快照当前态（它已经是最新一条）。
        """
        version_no = await self.version_repo.next_version_no(resume.id)
        await self.version_repo.create({
            "resume_id": resume.id,
            "version_no": version_no,
            "label": label,
            "resume_data": data,
            "match_score": match_score,
        })
        await self.version_repo.prune_oldest(resume.id, MAX_VERSIONS)

    async def list_versions(self, resume_id: uuid.UUID, user_id: uuid.UUID) -> list:
        await self.get(resume_id, user_id)  # 所有权校验
        return await self.version_repo.list_meta_by_resume(resume_id)

    async def get_version(self, resume_id: uuid.UUID, user_id: uuid.UUID, version_id: uuid.UUID):
        await self.get(resume_id, user_id)
        version = await self.version_repo.get_by_resume(resume_id, version_id)
        if version is None:
            raise NotFoundException("版本不存在")
        return version

    async def rollback_version(self, resume_id: uuid.UUID, user_id: uuid.UUID, version_id: uuid.UUID) -> Resume:
        """把某个历史版本的内容恢复为当前内容，并作为新版本追加（历史只增不改）。"""
        resume = await self.get(resume_id, user_id)
        if resume.status not in {"generated", "exported"}:
            raise BadRequestException("只有生成成功的简历才能回滚版本")
        version = await self.version_repo.get_by_resume(resume_id, version_id)
        if version is None:
            raise NotFoundException("版本不存在")
        data = dict(version.resume_data or {})
        existing = resume.resume_data or {}
        # match_details 跟随内容一起回滚；缺失时保留当前值兜底
        if not data.get("match_details"):
            data["match_details"] = existing.get("match_details") or []
        await self._snapshot(resume, "rollback", data, version.match_score)
        await self.repo.update(resume, {
            "resume_data": data,
            "match_score": version.match_score,
            "pdf_path": None,
            "status": "generated",
        })
        await self.db.commit()
        logger.info("[版本] resume=%s 已回滚到版本 %s（no=%s）", resume_id, version_id, version.version_no)
        return resume

    # ---------------- 导出 PDF ----------------
    async def export_pdf(self, resume_id: uuid.UUID, user_id: uuid.UUID, template: str | None = None) -> str:
        resume = await self.get(resume_id, user_id)
        template_name = template or resume.html_template or "technical"
        output_path = ensure_export_path(version_name_to_filename(resume.version_name))
        page_limit = int((resume.preferences or {}).get("page_limit") or 1)
        safe_data = exportable_resume_data(resume.resume_data)
        await resume_renderer.render_to_pdf(safe_data, template_name, output_path, page_limit=page_limit)
        await self.repo.update(resume, {"pdf_path": output_path, "status": "exported", "html_template": template_name})
        await self.db.commit()
        return output_path

    # ---------------- 补强建议（用户确认后合并） ----------------
    async def apply_enhancements(
        self, resume_id: uuid.UUID, user_id: uuid.UUID, placements: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """把用户确认的建议 bullet 融入已有公司经历，不创建新项目或公司。"""
        resume = await self.get(resume_id, user_id)
        if resume.status not in {"generated", "exported"}:
            raise BadRequestException("只有生成成功的简历才能优化经历")
        candidates = resume.enhancements or []
        if not candidates:
            raise BadRequestException("这份简历没有可融入的经历建议")
        if not placements:
            raise BadRequestException("请至少选择一条经历建议")

        profile = await ProfileService(self.db).profile_to_dict(user_id)
        work_sources = profile.get("work_experiences") or []
        # 回写档案用：与 profile_to_dict 相同的过滤/排序，保证 source_index 对得上 ORM 行
        profile_repo = ProfileRepository(self.db)
        profile_row = await profile_repo.get_full_by_user_id(user_id)
        orm_work = [
            w for w in sorted(profile_row.work_experiences, key=lambda x: x.order_index)
            if w.visibility
        ] if profile_row else []
        data = dict(resume.resume_data or {})
        sections = [dict(section) for section in (data.get("sections") or [])]
        experience = next((section for section in sections if section.get("type") == "experience"), None)
        if experience is None:
            raise BadRequestException("当前简历没有可挂载的工作经历，请先完善档案并重新生成")
        work_items = [dict(item) for item in (experience.get("items") or [])]

        used: set[int] = set()
        applied = 0
        added_bullets = 0
        written_back = 0
        confirmed_at = datetime.now().isoformat(timespec="seconds")
        for placement in placements:
            index = placement.get("index")
            target_ref = str(placement.get("target_source_ref") or "")
            if not isinstance(index, int) or isinstance(index, bool) or index < 0 or index >= len(candidates):
                raise BadRequestException(f"经历建议序号越界：{index}")
            if index in used:
                continue
            prefix = "work_experiences["
            if not (target_ref.startswith(prefix) and target_ref.endswith("]")):
                raise BadRequestException("挂载公司无效，请从已有工作经历中选择")
            try:
                source_index = int(target_ref[len(prefix):-1])
            except ValueError as exc:
                raise BadRequestException("挂载公司无效，请从已有工作经历中选择") from exc
            if source_index < 0 or source_index >= len(work_sources):
                raise BadRequestException("所选工作经历不存在或已被删除")

            source = work_sources[source_index]
            target = next((item for item in work_items if item.get("source_ref") == target_ref), None)
            if target is None:
                company = str(source.get("company") or "").strip().casefold()
                position = str(source.get("position") or "").strip().casefold()
                target = next((
                    item for item in work_items
                    if str(item.get("company") or "").strip().casefold() == company
                    and (not position or str(item.get("position") or "").strip().casefold() == position)
                ), None)
            if target is None:
                raise BadRequestException("所选公司经历未包含在当前简历中，请重新生成后再融入")

            candidate = candidates[index]
            raw_bullets = candidate.get("suggested_bullets")
            if not isinstance(raw_bullets, list):
                project = candidate.get("project") if isinstance(candidate.get("project"), dict) else {}
                raw_bullets = project.get("bullets") or []
            suggestions = [str(value).strip()[:500] for value in raw_bullets if str(value).strip()]
            existing = list(target.get("bullets") or [])
            normalized = {"".join(str(value).split()).casefold() for value in existing}
            additions = [
                value for value in suggestions
                if "".join(value.split()).casefold() not in normalized
            ]
            if additions:
                target["bullets"] = existing + additions
                target["relevance"] = max(
                    int(target.get("relevance") or 0),
                    {"high": 10, "medium": 8, "low": 7}.get(candidate.get("risk"), 8),
                )
                audit = list(target.get("confirmed_enhancements") or [])
                audit.append({
                    "candidate_index": index,
                    "target_source_ref": target_ref,
                    "confirmed_at": confirmed_at,
                    "gap": str(candidate.get("gap") or "")[:300],
                    "bullets_added": len(additions),
                })
                target["confirmed_enhancements"] = audit
                added_bullets += len(additions)
                # 用户勾选「同时补充到档案中心」：写入 WorkExperience.achievements（去重），
                # 之后所有简历生成都能看到这段经历，不必每份简历重复确认
                if placement.get("write_back_profile") and profile_row and source_index < len(orm_work):
                    orm_item = orm_work[source_index]
                    existing_ach = list(orm_item.achievements or [])
                    seen = {"".join(str(v).split()).casefold() for v in existing_ach}
                    seen |= {"".join(str(v).split()).casefold() for v in (orm_item.description or [])}
                    fresh = [v for v in additions if "".join(v.split()).casefold() not in seen]
                    if fresh:
                        await profile_repo.update_sub_entity(
                            WorkExperience, orm_item.id, profile_row.id,
                            {"achievements": existing_ach + fresh},
                        )
                        written_back += len(fresh)
            used.add(index)
            applied += 1

        experience["items"] = work_items
        data["sections"] = sections
        remaining = [candidate for index, candidate in enumerate(candidates) if index not in used]
        await self._ensure_baseline(resume)
        await self._snapshot(resume, "enhancement_applied", data, resume.match_score)
        await self.repo.update(resume, {
            "resume_data": data,
            "enhancements": remaining,
            "status": "generated",
            "pdf_path": None,
        })
        await self.db.commit()
        return {
            "applied": applied,
            "added_bullets": added_bullets,
            "written_back_to_profile": written_back,
            "remaining": len(remaining),
        }

    # ---------------- 诊断 ----------------
    async def diagnosis(self, resume_text: str, keywords_hint: list[str] | None = None) -> dict[str, Any]:
        ai = await self._ai()
        return await ai.resume_diagnosis(resume_text, keywords_hint)

    # ---------------- 面试 Q&A ----------------
    async def interview_qa(self, resume_id: uuid.UUID, user_id: uuid.UUID, question_count: int = 8) -> dict[str, Any]:
        resume = await self.get(resume_id, user_id)
        jd_parsed: dict[str, Any] = {}
        if resume.jd_id:
            jd = await self.jd_repo.get(resume.jd_id)
            jd_parsed = (jd.parsed_data if jd else None) or {}
        ai = await self._ai()
        return await ai.generate_interview_qa(resume.resume_data, jd_parsed, question_count)


async def sweep_stale_pending() -> int:
    """启动清扫：后台任务存在内存里，进程重启即丢失；把孤儿 pending 置为 failed，避免前端永远显示“生成中”。"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(Resume)
            .where(Resume.status == "pending")
            .values(status="failed", error_message="服务重启导致生成任务中断，请在任务列表点「重试」重新生成")
        )
        await db.commit()
        return result.rowcount or 0


async def reap_stale_pending(stale_after: float = STALE_AFTER) -> int:
    """把“本进程没有在跑、却一直停在 pending”的任务判定为中断并置为 failed。

    与启动清扫的区别：这是运行期持续生效的自愈，覆盖 uvicorn --reload 杀掉子进程、
    进程被 OOM/强杀、任务异常静默退出等所有“启动之后才发生的中断”场景。
    """
    cutoff = datetime.now() - timedelta(seconds=stale_after)
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(Resume).where(Resume.status == "pending"))).scalars().all()
        # 用 updated_at 而非 created_at：重试是原地重跑已有行，created_at 停留在首次创建时间，
        # 拿它当起点会在别的进程/刚重启的瞬间把正常任务误判成孤儿。
        stale = [
            r for r in rows
            if (_as_local_naive(r.updated_at) or cutoff) < cutoff and str(r.id) not in _RUNNING
        ]
        if not stale:
            return 0
        for r in stale:
            r.status = "failed"
            r.error_message = "生成任务中断（进程重启或长时间无响应），请点「重试」重新生成"
            logger.warning("[巡检] resume=%s 判定为孤儿任务，已置为失败", r.id)
        await db.commit()
        return len(stale)


async def watchdog(interval: float = WATCHDOG_INTERVAL) -> None:
    """常驻巡检协程：周期性回收孤儿 pending 任务（简历 + 面试准备），随应用生命周期启停。"""
    logger.info("生成任务巡检已启动：每 %.0f 秒检查一次，pending 超过 %.0f 秒判定为中断",
                interval, STALE_AFTER)
    while True:
        try:
            await asyncio.sleep(interval)
            await reap_stale_pending()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("生成任务巡检异常，下个周期重试")

        # 面试准备同样是后台任务，一起回收；单独 try 避免互相影响
        try:
            from app.services.interview_service import reap_stale_preps
            await reap_stale_preps()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("面试准备巡检异常，下个周期重试")


async def _run_generation_bg(resume_id: uuid.UUID, user_id: uuid.UUID, jd_id: uuid.UUID, preferences: dict[str, Any]) -> None:
    """后台任务：独立会话里执行 AI 生成，成功写结果，失败记原因；整体超时上限 15 分钟。"""
    _RUNNING[str(resume_id)] = time.time()
    t0 = time.time()
    logger.info("[生成任务] resume=%s 开始（超时上限 %d 秒）", resume_id, GEN_TIMEOUT)
    try:
        await asyncio.wait_for(
            _run_generation_impl(resume_id, user_id, jd_id, preferences), timeout=GEN_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.warning("[生成任务] resume=%s 超时（%.0f 秒）", resume_id, time.time() - t0)
        await _mark_failed(resume_id, f"生成超时（{GEN_TIMEOUT // 60} 分钟），请稍后重试")
    except Exception as exc:  # 任何异常都转成失败状态，不让后台任务静默丢失
        logger.exception("[生成任务] resume=%s 失败（%.0f 秒）", resume_id, time.time() - t0)
        await _mark_failed(resume_id, str(exc)[:2000])
    finally:
        _RUNNING.pop(str(resume_id), None)


async def _mark_failed(resume_id: uuid.UUID, message: str) -> None:
    try:
        async with AsyncSessionLocal() as db:
            resume = await db.get(Resume, resume_id)
            if resume is not None:
                resume.status = "failed"
                resume.error_message = message
                await db.commit()
    except Exception:
        logger.exception("简历 %s 失败状态落库也失败", resume_id)


async def _run_generation_impl(resume_id: uuid.UUID, user_id: uuid.UUID, jd_id: uuid.UUID, preferences: dict[str, Any]) -> None:
    async with AsyncSessionLocal() as db:
        svc = ResumeService(db)
        jd = await svc.jd_repo.get(jd_id)
        if jd is None or not jd.parsed_data:
            raise BadRequestException("JD 不存在或尚未解析")
        profile_dict = await ProfileService(db).profile_to_dict(user_id)
        n_edu, n_work, n_skill = (len(profile_dict.get(k) or []) for k in ("educations", "work_experiences", "skills"))
        # 空档案必然产出空简历，别浪费一轮几分钟的推理，也别给用户一个假的成功状态
        if is_profile_empty(profile_dict):
            raise BadRequestException(
                "档案为空，无法生成简历：请先到「我的档案」填写教育、工作或技能等信息后再生成"
            )
        logger.info("[生成任务] resume=%s 档案就绪（教育 %s / 工作 %s / 技能 %s），开始调用 Kimi…", resume_id, n_edu, n_work, n_skill)
        t_ai = time.time()
        ai = await svc._ai()
        result = await ai.generate_resume(
            profile_dict, jd.parsed_data, preferences, jd_raw_text=jd.raw_text or "",
        )
        logger.info("[生成任务] resume=%s Kimi 返回（%.0f 秒，tokens=%s）", resume_id, time.time() - t_ai, ai.last_usage)

        resume = await svc.repo.get(resume_id)
        if resume is None:
            logger.info("简历 %s 已被删除，放弃后台生成结果", resume_id)
            return
        resume_payload = sanitize_resume_facts(result.get("resume"), profile_dict)
        match_details = sanitize_match_details(result.get("match_details"), profile_dict)
        resume_payload["match_details"] = match_details
        deterministic_score = match_score_from_details(match_details)
        # AI 偶尔只回一个 header、sections 为空的空壳。照单全收就是「生成成功但一片空白」，
        # 用户根本不知道该往哪儿查。宁可失败并说明原因，也不要假成功。
        if not resume_payload.get("sections"):
            raise BadRequestException(
                "AI 返回了空简历（没有任何内容模块）。请完善档案、或调整 JD 与页数限制后重试"
            )
        validate_resume_content_budget(resume_payload, profile_dict)
        await svc.repo.update(resume, {
            "version_name": result.get("version_name") or resume.version_name,
            "resume_data": resume_payload,
            "match_score": deterministic_score if deterministic_score is not None else result.get("match_score"),
            "highlights": result.get("highlights") or [],
            "gaps": result.get("gaps") or [],
            "suggestions": result.get("suggestions") or [],
            # 候选补强项目单独存，不进 resume_data —— 是否采用由用户逐条确认
            "enhancements": sanitize_enhancements(result.get("enhancements")),
            "status": "generated",
            "error_message": None,
        })
        # 版本历史起点：AI 落地的每一版内容都留档，重试覆盖前旧内容仍可回溯
        await svc._snapshot(resume, "ai_generated", resume_payload, resume.match_score)
        await db.commit()
        logger.info("[生成任务] resume=%s 完成 ✅ match=%s", resume_id, result.get("match_score"))
