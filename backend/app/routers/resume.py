"""简历路由（指令 5 路由 2/3 + 诊断 + 面试 Q&A，指令 6 导出接口）。"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.common import success
from app.schemas.resume import (
    EnhancementApplyRequest, InterviewPrepResponse, InterviewPrepareRequest,
    InterviewQARequest, ResumeDataUpdateRequest, ResumeDiagnosisRequest,
    ResumeExportRequest, ResumeGenerateRequest, ResumeGenerateResponse,
    ResumeResponse, ResumeVersionDetail, ResumeVersionMeta,
)
from app.services.interview_service import InterviewService
from app.services.resume_service import ResumeService
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/resumes", tags=["简历"])


def _resume_dump(resume) -> dict:
    """ORM → dict，附带 has_interview_prep 标记。"""
    data = ResumeResponse.model_validate(resume).model_dump(mode="json")
    data["has_interview_prep"] = resume.interview_prep is not None
    return data


@router.post("/generate", summary="提交后台生成定制简历（立即返回，异步出结果）")
async def generate_resume(data: ResumeGenerateRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    resume = await ResumeService(db).generate(user.id, data.jd_id, data.preferences.model_dump())
    return success(ResumeGenerateResponse(
        id=resume.id, version_name=resume.version_name, match_score=resume.match_score,
        highlights=resume.highlights, gaps=resume.gaps, suggestions=resume.suggestions,
        resume_data=resume.resume_data, status=resume.status, error_message=resume.error_message,
    ).model_dump(mode="json"), "生成任务已提交，请稍后回来查看")


@router.post("/{resume_id}/retry", summary="重试失败/中断的生成任务（复用原记录）")
async def retry_resume(resume_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    resume = await ResumeService(db).retry(resume_id, user.id)
    return success(_resume_dump(resume), "已重新提交生成任务，完成后列表自动刷新")


@router.post("/diagnosis", summary="简历诊断（粘贴简历文本）")
async def diagnose_resume(data: ResumeDiagnosisRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await ResumeService(db).diagnosis(data.resume_text, data.keywords_hint)
    return success(result)


@router.get("", summary="简历版本列表")
async def list_resumes(
    offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    items = await ResumeService(db).list(user.id, offset, limit)
    return success([_resume_dump(i) for i in items])


@router.get("/{resume_id}", summary="简历详情")
async def get_resume(resume_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    resume = await ResumeService(db).get(resume_id, user.id)
    return success(_resume_dump(resume))


@router.delete("/{resume_id}", summary="删除简历版本")
async def delete_resume(resume_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await ResumeService(db).delete(resume_id, user.id)
    return success(None, "删除成功")


@router.put("/{resume_id}/data", summary="保存编辑后的简历内容（不调 AI）")
async def update_resume_data(resume_id: uuid.UUID, data: ResumeDataUpdateRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    resume = await ResumeService(db).update_data(resume_id, user.id, data.resume_data)
    return success(_resume_dump(resume), "已保存编辑，PDF 需重新导出")


@router.get("/{resume_id}/stats", summary="简历统计（字数/预计页数/JD 关键词覆盖）")
async def resume_stats(resume_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return success(await ResumeService(db).stats(resume_id, user.id))


# ---------------- 版本历史 ----------------
@router.get("/{resume_id}/versions", summary="版本历史列表（仅元信息）")
async def list_resume_versions(resume_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    versions = await ResumeService(db).list_versions(resume_id, user.id)
    return success([ResumeVersionMeta.model_validate(v).model_dump(mode="json") for v in versions])


@router.get("/{resume_id}/versions/{version_id}", summary="版本详情（含完整内容，供 diff）")
async def get_resume_version(resume_id: uuid.UUID, version_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    version = await ResumeService(db).get_version(resume_id, user.id, version_id)
    return success(ResumeVersionDetail.model_validate(version).model_dump(mode="json"))


@router.post("/{resume_id}/versions/{version_id}/rollback", summary="回滚到指定版本（作为新版本追加）")
async def rollback_resume_version(resume_id: uuid.UUID, version_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    resume = await ResumeService(db).rollback_version(resume_id, user.id, version_id)
    return success(_resume_dump(resume), "已回滚到所选版本，PDF 需重新导出")


@router.post("/{resume_id}/export", summary="导出简历 PDF")
async def export_resume(resume_id: uuid.UUID, data: ResumeExportRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """渲染 HTML 并导出 A4 PDF，返回文件下载流。"""
    pdf_path = await ResumeService(db).export_pdf(resume_id, user.id, data.template)
    return FileResponse(pdf_path, media_type="application/pdf", filename=Path(pdf_path).name)


@router.post("/{resume_id}/enhancements/apply", summary="把职责建议融入已有工作经历")
async def apply_enhancements(
    resume_id: uuid.UUID,
    data: EnhancementApplyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户逐条确认后，才把 AI 的候选补强项目写进简历的项目模块。

    候选内容本质是推测草稿，所以生成时绝不会自动进简历 —— 必须走这里由用户显式勾选。
    """
    result = await ResumeService(db).apply_enhancements(
        resume_id, user.id, [placement.model_dump() for placement in data.placements],
    )
    return success(result, f"已将 {result['applied']} 条建议融入现有工作经历")


@router.post("/{resume_id}/interview-qa", summary="生成面试 Q&A")
async def interview_qa(resume_id: uuid.UUID, data: InterviewQARequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await ResumeService(db).interview_qa(resume_id, user.id, data.question_count)
    return success(result)


# ---------------- 面试准备（调研 + 提纲 + 题库，持久化） ----------------
@router.post("/{resume_id}/interview/prepare", summary="一键生成面试准备（后台任务，提交即返回）")
async def prepare_interview(resume_id: uuid.UUID, data: InterviewPrepareRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    prep = await InterviewService(db).prepare(resume_id, user.id, data.question_count)
    return success(InterviewPrepResponse.model_validate(prep).model_dump(mode="json"),
                   "面试准备任务已提交，预计需要 3–8 分钟，完成后自动刷新")


@router.get("/{resume_id}/interview", summary="查看面试准备（含生成状态）")
async def get_interview_prep(resume_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    prep = await InterviewService(db).get(resume_id, user.id)
    if prep is None:
        return success(None)
    return success(InterviewPrepResponse.model_validate(prep).model_dump(mode="json"))


@router.post("/{resume_id}/interview/regenerate", summary="重新生成面试准备（后台任务）")
async def regenerate_interview(resume_id: uuid.UUID, data: InterviewPrepareRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    prep = await InterviewService(db).prepare(resume_id, user.id, data.question_count)
    return success(InterviewPrepResponse.model_validate(prep).model_dump(mode="json"),
                   "已重新提交生成任务，完成后自动刷新")
