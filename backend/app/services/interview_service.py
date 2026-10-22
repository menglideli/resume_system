"""面试准备业务层：一键生成岗位调研 + 面试提纲 + 题库并持久化（一份简历一条）。

三段 AI 调用串行执行，推理模型下实测单段就要 2–4 分钟，总计可达 5–10 分钟。
这个量级放在同步 HTTP 请求里必然出问题：
  - 生产环境 Nginx 未配 proxy_read_timeout，默认 60 秒即返回 504；
  - 中途进程重启（uvicorn --reload / 崩溃）会丢掉全部已完成的段落，因为结果只在最后才落库。
因此与简历生成保持一致，改为「提交即返回 + 后台任务 + 状态轮询」。
"""
import asyncio
import logging
import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.interview_prep import InterviewPrep
from app.repositories.interview_prep_repo import InterviewPrepRepository
from app.repositories.jd_repo import JDRepository
from app.repositories.resume_repo import ResumeRepository
from app.services.ai_service import AIService
from app.services.config_service import ConfigService
from app.utils.exceptions import NotFoundException

logger = logging.getLogger("interview_service")

_BG_TASKS: set[asyncio.Task] = set()
# 本进程正在执行的准备任务：resume_id(str) → 启动时间戳，供巡检豁免
_RUNNING: dict[str, float] = {}

PREP_TIMEOUT = 900       # 单个准备任务总超时（秒）
PREP_STALE_AFTER = 600   # pending 超过该秒数且本进程无运行中任务 → 判定为孤儿


class InterviewService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = InterviewPrepRepository(db)
        self.resume_repo = ResumeRepository(db)
        self.jd_repo = JDRepository(db)

    async def _ai(self) -> AIService:
        """按运行时配置（system_config）构造 AI 客户端，未配置时回退 .env。"""
        return AIService(await ConfigService(self.db).get_effective_kimi_config())

    async def get(self, resume_id: uuid.UUID, user_id: uuid.UUID) -> InterviewPrep | None:
        await self._check_resume(resume_id, user_id)
        return await self.repo.get_by_resume(resume_id)

    async def prepare(self, resume_id: uuid.UUID, user_id: uuid.UUID, question_count: int = 10) -> InterviewPrep:
        """一键生成（已存在则整体覆盖）：提交后台任务并立即返回 pending 的记录。

        旧内容保留到新结果出来为止，避免生成失败把用户已有的准备清空。
        """
        await self._check_resume(resume_id, user_id)
        existing = await self.repo.get_by_resume(resume_id)
        # 幂等：同一简历已有任务在跑时不再重复提交，避免重复烧 token 和并发写同一行
        if str(resume_id) in _RUNNING:
            logger.warning("[面试准备] resume=%s 已有任务在执行，忽略重复提交", resume_id)
            return existing
        if existing is None:
            prep = await self.repo.create({
                "resume_id": resume_id,
                "research": {}, "outline": {}, "questions": [],
                "status": "pending",
            })
        else:
            prep = await self.repo.update(existing, {"status": "pending", "error_message": None})
        await self.db.commit()

        _RUNNING[str(resume_id)] = time.time()
        task = asyncio.create_task(_run_prep_bg(resume_id, question_count))
        _BG_TASKS.add(task)
        task.add_done_callback(_BG_TASKS.discard)
        logger.info("[面试准备] resume=%s 已提交后台任务（%s 题）", resume_id, question_count)
        return prep

    async def _check_resume(self, resume_id: uuid.UUID, user_id: uuid.UUID):
        resume = await self.resume_repo.get_by_user(resume_id, user_id)
        if resume is None:
            raise NotFoundException("简历不存在")
        return resume


async def reap_stale_preps(stale_after: float = PREP_STALE_AFTER) -> int:
    """回收「本进程没在跑却一直 pending」的面试准备任务（与简历生成同一套自愈逻辑）。"""
    from datetime import datetime, timedelta

    from app.services.resume_service import _as_local_naive

    cutoff = datetime.now() - timedelta(seconds=stale_after)
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(InterviewPrep).where(InterviewPrep.status == "pending"))).scalars().all()
        # 用 updated_at 而非 created_at：重新生成时行已存在，created_at 停留在首次创建时间，
        # 拿它当起点会把刚提交的任务误判成孤儿；prepare() 置 pending 会刷新 updated_at。
        stale = [
            r for r in rows
            if (_as_local_naive(r.updated_at) or cutoff) < cutoff and str(r.resume_id) not in _RUNNING
        ]
        if not stale:
            return 0
        for r in stale:
            r.status = "failed"
            r.error_message = "生成任务中断（进程重启或长时间无响应），请重新生成"
            logger.warning("[巡检] 面试准备 resume=%s 判定为孤儿任务，已置为失败", r.resume_id)
        await db.commit()
        return len(stale)


async def _mark_failed(resume_id: uuid.UUID, message: str) -> None:
    try:
        async with AsyncSessionLocal() as db:
            repo = InterviewPrepRepository(db)
            prep = await repo.get_by_resume(resume_id)
            if prep is not None:
                prep.status = "failed"
                prep.error_message = message
                await db.commit()
    except Exception:
        logger.exception("面试准备 %s 失败状态落库也失败", resume_id)


async def _run_prep_bg(resume_id: uuid.UUID, question_count: int) -> None:
    _RUNNING[str(resume_id)] = time.time()
    t0 = time.time()
    logger.info("[面试准备] resume=%s 开始（超时上限 %d 秒）", resume_id, PREP_TIMEOUT)
    try:
        await asyncio.wait_for(_run_prep_impl(resume_id, question_count), timeout=PREP_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("[面试准备] resume=%s 超时（%.0f 秒）", resume_id, time.time() - t0)
        await _mark_failed(resume_id, f"生成超时（{PREP_TIMEOUT // 60} 分钟），请稍后重试")
    except Exception as exc:
        logger.exception("[面试准备] resume=%s 失败（%.0f 秒）", resume_id, time.time() - t0)
        await _mark_failed(resume_id, str(exc)[:2000])
    finally:
        _RUNNING.pop(str(resume_id), None)


async def _run_prep_impl(resume_id: uuid.UUID, question_count: int) -> None:
    async with AsyncSessionLocal() as db:
        svc = InterviewService(db)
        prep = await svc.repo.get_by_resume(resume_id)
        if prep is None:
            logger.info("面试准备 %s 已被删除，放弃后台生成结果", resume_id)
            return
        resume = await svc.resume_repo.get(resume_id)
        if resume is None:
            await _mark_failed(resume_id, "简历不存在")
            return

        jd_parsed: dict[str, Any] = {}
        if resume.jd_id:
            jd = await svc.jd_repo.get(resume.jd_id)
            jd_parsed = (jd.parsed_data if jd else None) or {}

        ai = await svc._ai()
        research = await ai.job_research(resume.resume_data, jd_parsed)
        outline = await ai.interview_outline(resume.resume_data, jd_parsed)
        qa = await ai.generate_interview_qa(resume.resume_data, jd_parsed, question_count)
        questions = qa.get("questions") or []

        await svc.repo.update(prep, {
            "research": research,
            "outline": outline,
            "questions": questions,
            "status": "generated",
            "error_message": None,
        })
        await db.commit()
        logger.info("[面试准备] resume=%s 完成 ✅ %s 题", resume_id, len(questions))
