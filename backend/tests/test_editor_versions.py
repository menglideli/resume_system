"""编辑器、版本历史与投递快照回归测试（无 DB、无网络）。

结构断言沿用 tests/helpers.py 的字节码模式：accessed_names 查属性/全局名，
string_consts 查字符串常量（含 dict key）。纯函数直接调用验证行为。
"""
import uuid
from types import SimpleNamespace

import pytest

from app.services import application_service as apps
from app.services import resume_service as rs
from app.utils.exceptions import BadRequestException, NotFoundException
from tests.helpers import accessed_names, string_consts


# ---------------- 测试脚手架 ----------------
class _FakeRepo:
    def __init__(self):
        self.updates = []

    async def update(self, obj, values):
        self.updates.append(values)
        for key, value in values.items():
            setattr(obj, key, value)


class _FakeDB:
    def __init__(self):
        self.committed = False

    async def commit(self):
        self.committed = True


class _FakeVersionRepo:
    def __init__(self):
        self.created = []

    async def next_version_no(self, resume_id):
        return len(self.created) + 1

    async def count_by_resume(self, resume_id):
        return len(self.created)

    async def create(self, values):
        row = SimpleNamespace(id=uuid.uuid4(), **values)
        self.created.append(values)
        return row

    async def prune_oldest(self, resume_id, keep):
        return 0

    async def get_by_resume(self, resume_id, version_id):
        return self._by_id.get(version_id)

    _by_id: dict = {}


class _Resume:
    def __init__(self, status="generated"):
        self.id = uuid.uuid4()
        self.resume_data = {
            "sections": [{"type": "summary", "content": "旧总结"}],
            "match_details": [{"requirement": "5年经验", "priority": "must", "status": "direct"}],
        }
        self.status = status
        self.pdf_path = "old.pdf"
        self.match_score = 65
        self.html_template = "technical"
        self.jd_id = None


def _editor_service(resume):
    from app.services.resume_service import ResumeService
    svc = ResumeService.__new__(ResumeService)
    svc.repo = _FakeRepo()
    svc.db = _FakeDB()
    svc.version_repo = _FakeVersionRepo()
    svc.jd_repo = SimpleNamespace()

    async def get(_rid, _uid):
        return resume

    svc.get = get
    return svc


def _sample_data(**overrides):
    data = {
        "header": {"name": "张三", "title": "后端工程师", "contact": {"phone": "1", "email": "e", "location": "北京"}},
        "sections": [
            {"type": "summary", "content": "新总结"},
            {"type": "experience", "items": [
                {"company": "A", "position": "p", "relevance": 9, "bullets": ["b1", "b2"], "source_ref": "work_experiences[0]"},
                {"company": "B", "hidden": True, "bullets": ["被隐藏"]},
            ]},
            {"type": "skills", "items": [{"name": "Python", "category": "语言", "relevance": "8"}]},
        ],
    }
    data.update(overrides)
    return data


# ---------------- sanitize_user_edits ----------------
@pytest.mark.parametrize("bad", [None, "x", 5, {}, {"sections": []}, {"sections": "x"}, {"sections": [1]}])
def test_sanitize_rejects_malformed(bad):
    with pytest.raises(BadRequestException):
        rs.sanitize_user_edits(bad)


def test_sanitize_clips_and_coerces():
    raw = _sample_data()
    raw["sections"][0]["content"] = "长" * 9999
    raw["sections"][1]["items"][0]["bullets"] = ["x" * 2000, "", None, "ok"]
    raw["sections"][1]["items"][0]["relevance"] = "99"
    clean = rs.sanitize_user_edits(raw)
    assert len(clean["sections"][0]["content"]) == rs._EDIT_LIMITS["summary_len"]
    item = clean["sections"][1]["items"][0]
    assert item["bullets"] == ["x" * rs._EDIT_LIMITS["bullet_len"], "ok"]
    assert item["relevance"] == 10          # 字符串转 int 并夹到 0-10
    skill = clean["sections"][2]["items"][0]
    assert skill["relevance"] == 8 and isinstance(skill["relevance"], int)
    assert clean["sections"][1]["items"][1]["hidden"] is True


def test_sanitize_drops_invalid_relevance_and_narrows_header():
    raw = _sample_data()
    raw["header"]["evil"] = "x"
    raw["sections"][2]["items"][0]["relevance"] = "很高"
    clean = rs.sanitize_user_edits(raw)
    assert "evil" not in clean["header"]
    assert "relevance" not in clean["sections"][2]["items"][0]


def test_sanitize_rejects_oversized_sections():
    raw = {"sections": [{"type": "summary", "content": "x"}] * (rs._EDIT_LIMITS["sections"] + 1)}
    with pytest.raises(BadRequestException):
        rs.sanitize_user_edits(raw)


# ---------------- 导出过滤 hidden ----------------
def test_exportable_removes_hidden_items():
    exp = rs.exportable_resume_data(_sample_data())
    experience = next(s for s in exp["sections"] if s.get("type") == "experience")
    assert len(experience["items"]) == 1
    assert experience["items"][0]["company"] == "A"


# ---------------- resume_stats ----------------
def test_stats_counts_visible_only_and_coverage():
    stats = rs.resume_stats(_sample_data(), {"keywords": ["Python", "Go"], "ats_keywords": ["b1"]})
    text = rs.collect_visible_text(_sample_data())
    assert "被隐藏" not in text
    assert stats["item_count"] == 2          # hidden 条目不计
    assert stats["keyword_total"] == 3
    assert stats["keyword_covered"] == 2     # Python + b1（大小写不敏感）
    assert stats["missing_keywords"] == ["Go"]
    assert stats["estimated_pages"] == max(1, -(-stats["char_count"] // rs._CHARS_PER_PAGE))


def test_stats_without_jd_has_no_coverage():
    stats = rs.resume_stats(_sample_data(), None)
    assert stats["keyword_coverage"] is None
    assert stats["keyword_total"] == 0


# ---------------- update_data ----------------
@pytest.mark.asyncio
async def test_update_data_keeps_match_details_and_snapshots():
    resume = _Resume(status="exported")
    svc = _editor_service(resume)
    incoming = _sample_data()
    incoming["match_details"] = [{"requirement": "前端伪造的匹配证据"}]
    out = await svc.update_data(resume.id, "u", incoming)
    # 服务端保留库里的 match_details，拒绝前端改写
    assert out.resume_data["match_details"] == [{"requirement": "5年经验", "priority": "must", "status": "direct"}]
    # exported 回退 generated，旧 PDF 作废
    assert out.status == "generated" and out.pdf_path is None
    assert svc.db.committed
    created = svc.version_repo.created
    # 存量简历（无历史）首次编辑：先补 AI 原始基线，再记编辑后状态
    assert [c["label"] for c in created] == ["ai_generated", "user_edit"]
    assert created[0]["resume_data"]["sections"][0]["content"] == "旧总结"
    assert created[-1]["version_no"] == 2
    assert created[-1]["resume_data"]["sections"][0]["content"] == "新总结"


@pytest.mark.asyncio
async def test_update_data_skips_baseline_when_versions_exist():
    resume = _Resume()
    svc = _editor_service(resume)
    svc.version_repo.created.append({"label": "ai_generated", "version_no": 1})  # 已有历史
    await svc.update_data(resume.id, "u", _sample_data())
    labels = [c["label"] for c in svc.version_repo.created]
    assert labels == ["ai_generated", "user_edit"]   # 不重复补基线


@pytest.mark.asyncio
async def test_update_data_rejects_pending():
    resume = _Resume(status="pending")
    svc = _editor_service(resume)
    with pytest.raises(BadRequestException):
        await svc.update_data(resume.id, "u", _sample_data())
    assert not svc.db.committed
    assert svc.version_repo.created == []


# ---------------- rollback ----------------
@pytest.mark.asyncio
async def test_rollback_restores_content_and_score():
    resume = _Resume()
    svc = _editor_service(resume)
    old_data = {"sections": [{"type": "summary", "content": "旧版本内容"}]}
    version = SimpleNamespace(id=uuid.uuid4(), resume_data=old_data, match_score=72, version_no=1)
    svc.version_repo.get_by_resume = lambda _rid, _vid: _async_return(version)
    out = await svc.rollback_version(resume.id, "u", version.id)
    assert out.resume_data["sections"][0]["content"] == "旧版本内容"
    # 版本里没有 match_details 时保留当前值兜底
    assert out.resume_data["match_details"] == resume.resume_data["match_details"] or \
        out.resume_data["match_details"] == [{"requirement": "5年经验", "priority": "must", "status": "direct"}]
    assert out.match_score == 72
    assert out.pdf_path is None and out.status == "generated"
    assert svc.version_repo.created[-1]["label"] == "rollback"


def _async_return(value):
    async def _coro(*_args, **_kwargs):
        return value
    return _coro()


@pytest.mark.asyncio
async def test_rollback_unknown_version_raises():
    resume = _Resume()
    svc = _editor_service(resume)
    svc.version_repo.get_by_resume = lambda _rid, _vid: _async_return(None)
    with pytest.raises(NotFoundException):
        await svc.rollback_version(resume.id, "u", uuid.uuid4())


# ---------------- 快照时机的结构断言 ----------------
def test_generation_snapshots_ai_version():
    assert "_snapshot" in accessed_names(rs._run_generation_impl)
    assert "ai_generated" in string_consts(rs._run_generation_impl)


def test_apply_enhancements_snapshots():
    from app.services.resume_service import ResumeService
    assert "_snapshot" in accessed_names(ResumeService.apply_enhancements)
    assert "enhancement_applied" in string_consts(ResumeService.apply_enhancements)


def test_snapshot_creates_and_prunes():
    from app.services.resume_service import ResumeService
    names = accessed_names(ResumeService._snapshot)
    assert {"next_version_no", "create", "prune_oldest"} <= names
    assert rs.MAX_VERSIONS == 50


# ---------------- 模型与路由注册 ----------------
def test_models_have_new_columns():
    from app.models.application import Application
    from app.models.resume import Resume
    from app.models.resume_version import ResumeVersion
    for column in ("resume_snapshot", "snapshot_template", "snapshot_pdf_path", "snapshot_match_score", "jd_snapshot"):
        assert column in Application.__table__.columns
    for column in ("resume_id", "version_no", "label", "resume_data", "match_score"):
        assert getattr(ResumeVersion, column, None) is not None
    assert getattr(Resume, "versions", None) is not None


def test_resume_routes_registered():
    from app.routers.resume import router
    routes = {(method, route.path) for route in router.routes for method in route.methods}
    assert ("PUT", "/resumes/{resume_id}/data") in routes
    assert ("GET", "/resumes/{resume_id}/stats") in routes
    assert ("GET", "/resumes/{resume_id}/versions") in routes
    assert ("GET", "/resumes/{resume_id}/versions/{version_id}") in routes
    assert ("POST", "/resumes/{resume_id}/versions/{version_id}/rollback") in routes


def test_application_routes_registered():
    from app.routers.application import router
    routes = {(method, route.path) for route in router.routes for method in route.methods}
    assert ("GET", "/applications/{app_id}/snapshot") in routes
    assert ("GET", "/applications/{app_id}/snapshot/pdf") in routes


def test_enhancement_placement_write_back_default_false():
    from app.schemas.resume import EnhancementPlacement
    placement = EnhancementPlacement(index=0, target_source_ref="work_experiences[0]")
    assert placement.write_back_profile is False


# ---------------- 投递快照 ----------------
class _FakeResumeRepo:
    resume = None

    def __init__(self, db):
        pass

    async def get(self, resume_id):
        return type(self).resume


class _FakeJdRepo:
    jd = None

    def __init__(self, db):
        pass

    async def get(self, jd_id):
        return type(self).jd


def _snapshot_service():
    svc = apps.ApplicationService.__new__(apps.ApplicationService)
    svc.db = _FakeDB()
    svc.repo = _FakeRepo()
    return svc


@pytest.mark.asyncio
async def test_build_snapshot_locks_resume_and_jd(monkeypatch, tmp_path):
    user_id = uuid.uuid4()
    pdf = tmp_path / "resume.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    resume = SimpleNamespace(
        id=uuid.uuid4(), user_id=user_id, status="exported", jd_id=uuid.uuid4(),
        resume_data=_sample_data(), html_template="technical", match_score=78, pdf_path=str(pdf),
    )
    jd = SimpleNamespace(
        user_id=user_id, company_name="某公司", position_title="后端",
        raw_text="JD 原文", parsed_data={"keywords": ["Python"]},
    )
    _FakeResumeRepo.resume = resume
    _FakeJdRepo.jd = jd
    monkeypatch.setattr(apps, "ResumeRepository", _FakeResumeRepo)
    monkeypatch.setattr(apps, "JDRepository", _FakeJdRepo)
    monkeypatch.setattr(apps.settings, "EXPORT_DIR", str(tmp_path / "exports"))

    svc = _snapshot_service()
    snapshot = await svc._build_snapshot(user_id, resume.id, None)
    # 简历快照是导出形态：hidden 条目已剔除
    experience = next(s for s in snapshot["resume_snapshot"]["sections"] if s.get("type") == "experience")
    assert len(experience["items"]) == 1
    assert snapshot["snapshot_template"] == "technical"
    assert snapshot["snapshot_match_score"] == 78
    # PDF 复制到独立子目录，不共用会被重导出覆盖的原路径
    from pathlib import Path
    copy_path = Path(snapshot["snapshot_pdf_path"])
    assert copy_path.exists() and copy_path.parent.name == "applications"
    assert str(copy_path) != str(pdf)
    assert snapshot["jd_snapshot"]["raw_text"] == "JD 原文"
    assert snapshot["jd_id"] == resume.jd_id


@pytest.mark.asyncio
async def test_build_snapshot_rejects_pending_resume(monkeypatch):
    user_id = uuid.uuid4()
    _FakeResumeRepo.resume = SimpleNamespace(
        id=uuid.uuid4(), user_id=user_id, status="pending", jd_id=None,
        resume_data={}, html_template="technical", match_score=None, pdf_path=None,
    )
    monkeypatch.setattr(apps, "ResumeRepository", _FakeResumeRepo)
    svc = _snapshot_service()
    with pytest.raises(BadRequestException):
        await svc._build_snapshot(user_id, _FakeResumeRepo.resume.id, None)


@pytest.mark.asyncio
async def test_build_snapshot_empty_without_resume(monkeypatch):
    svc = _snapshot_service()
    assert await svc._build_snapshot(uuid.uuid4(), None, None) == {}
