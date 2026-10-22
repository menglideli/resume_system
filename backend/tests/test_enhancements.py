"""经历优化回归测试：候选只能在用户确认后融入已有公司 bullet。"""
import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services import resume_service as rs


def _candidate(text="负责 Windows Server 运维"):
    return {
        "gap": "JD 要求 Windows Server",
        "basis": "已有基础设施运维经历",
        "risk": "medium",
        "target_source_ref": "work_experiences[0]",
        "suggested_bullets": [text],
    }


def _legacy_candidate(text="负责 VMware 虚拟化平台维护"):
    return {
        "gap": "JD 要求虚拟化",
        "basis": "旧版项目候选",
        "risk": "high",
        "project": {"name": "旧项目名", "role": "旧角色", "period": "旧周期", "bullets": [text]},
    }


def test_sanitize_new_candidate_and_risk():
    out = rs.sanitize_enhancements([_candidate()])
    assert out[0]["target_source_ref"] == "work_experiences[0]"
    assert out[0]["suggested_bullets"] == ["负责 Windows Server 运维"]
    assert out[0]["legacy"] is False


def test_sanitize_legacy_candidate_keeps_only_bullets():
    out = rs.sanitize_enhancements([_legacy_candidate()])
    assert out[0]["target_source_ref"] == ""
    assert out[0]["suggested_bullets"] == ["负责 VMware 虚拟化平台维护"]
    assert out[0]["legacy"] is True
    assert "project" not in out[0]


def test_sanitize_drops_malformed_and_empty_bullets():
    assert rs.sanitize_enhancements(None) == []
    assert rs.sanitize_enhancements(["x", {}, {"suggested_bullets": None}]) == []
    invalid_ref = _candidate()
    invalid_ref["target_source_ref"] = "projects[0]"
    assert rs.sanitize_enhancements([invalid_ref])[0]["target_source_ref"] == ""


def test_sanitize_caps_list_and_normalizes_values():
    raw = [_candidate(f"建议 {i}") for i in range(9)]
    raw[0]["risk"] = "极高"
    raw[0]["suggested_bullets"] = ["有效", "", None, 123]
    out = rs.sanitize_enhancements(raw)
    assert len(out) == rs.MAX_ENHANCEMENTS
    assert out[0]["risk"] == "medium"
    assert out[0]["suggested_bullets"] == ["有效", "123"]


def test_generation_stores_candidates_separately():
    from tests.helpers import accessed_names, string_consts
    assert "enhancements" in string_consts(rs._run_generation_impl)
    assert "sanitize_enhancements" in accessed_names(rs._run_generation_impl)


def test_null_json_fields_serialize_for_legacy_rows():
    from app.schemas.resume import ResumeResponse
    now = datetime.now()
    row = SimpleNamespace(
        id=uuid.uuid4(), user_id=uuid.uuid4(), jd_id=None, version_name="旧简历",
        resume_data={"sections": []}, match_score=None, highlights=[], gaps=[], suggestions=[],
        html_template="technical", preferences=None, pdf_path=None, status="generated",
        error_message=None, enhancements=None, has_interview_prep=False,
        created_at=now, updated_at=now,
    )
    out = ResumeResponse.model_validate(row, from_attributes=True)
    assert out.enhancements == []
    assert out.preferences == {}


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
    """版本快照仓储桩：记录每次 create，供断言快照时机与内容。"""

    def __init__(self):
        self.created = []

    async def next_version_no(self, resume_id):
        return len(self.created) + 1

    async def count_by_resume(self, resume_id):
        return len(self.created)

    async def create(self, values):
        self.created.append(values)
        return SimpleNamespace(**values)

    async def prune_oldest(self, resume_id, keep):
        return 0

    async def get_by_resume(self, resume_id, version_id):
        for row in self.created:
            if row.get("id") == version_id:
                return SimpleNamespace(**row)
        return None


class _FakeProfileRepo:
    """档案仓储桩：profile_row 由测试注入；update_sub_entity 记录回写调用。"""

    profile_row = None
    updates: list = []

    def __init__(self, db):
        pass

    async def get_full_by_user_id(self, user_id):
        return type(self).profile_row

    async def update_sub_entity(self, model, entity_id, profile_id, data):
        type(self).updates.append((model, entity_id, profile_id, data))
        return SimpleNamespace(**data)


class _Resume:
    def __init__(self, enhancements, status="generated"):
        self.resume_data = {"sections": [{
            "type": "experience", "title": "工作经历", "items": [{
                "company": "真实公司", "position": "运维工程师", "period": "2020 - 至今",
                "source_ref": "work_experiences[0]", "relevance": 6,
                "bullets": ["负责基础设施日常运维"],
            }],
        }]}
        self.enhancements = enhancements
        self.status = status
        self.pdf_path = "old.pdf"
        self.match_score = 65
        self.id = uuid.uuid4()


def _make_service(resume, works=None, monkeypatch=None):
    from app.services.resume_service import ResumeService
    svc = ResumeService.__new__(ResumeService)
    svc.repo = _FakeRepo()
    svc.db = _FakeDB()
    svc.version_repo = _FakeVersionRepo()

    async def get(_rid, _uid):
        return resume

    svc.get = get
    profile_service = SimpleNamespace()

    async def profile_to_dict(_uid):
        return {"work_experiences": works or [{"company": "真实公司", "position": "运维工程师"}]}

    svc.get = get
    svc._test_profile_to_dict = profile_to_dict
    if monkeypatch is not None:
        # apply_enhancements 会为「回写档案」直接查 ORM 档案行；默认桩返回 None（不回写）
        _FakeProfileRepo.profile_row = None
        _FakeProfileRepo.updates = []
        monkeypatch.setattr(rs, "ProfileRepository", _FakeProfileRepo)
    return svc, profile_to_dict


async def _apply(monkeypatch, resume, placements, works=None):
    svc, profile_loader = _make_service(resume, works, monkeypatch)
    monkeypatch.setattr(rs.ProfileService, "profile_to_dict", lambda _self, uid: profile_loader(uid))
    result = await svc.apply_enhancements("r", "u", placements)
    return svc, result


@pytest.mark.asyncio
async def test_apply_adds_bullets_to_existing_company_only(monkeypatch):
    resume = _Resume([_candidate()])
    svc, result = await _apply(monkeypatch, resume, [{"index": 0, "target_source_ref": "work_experiences[0]"}])
    sections = resume.resume_data["sections"]
    assert [section["type"] for section in sections] == ["experience"]
    item = sections[0]["items"][0]
    assert item["company"] == "真实公司"
    assert item["position"] == "运维工程师"
    assert item["period"] == "2020 - 至今"
    assert item["bullets"][-1] == "负责 Windows Server 运维"
    assert item["confirmed_enhancements"][0]["target_source_ref"] == "work_experiences[0]"
    assert result["added_bullets"] == 1
    assert resume.pdf_path is None and resume.status == "generated"
    assert svc.db.committed


@pytest.mark.asyncio
async def test_apply_legacy_candidate_requires_explicit_company(monkeypatch):
    resume = _Resume([_legacy_candidate()])
    _, result = await _apply(monkeypatch, resume, [{"index": 0, "target_source_ref": "work_experiences[0]"}])
    assert result["added_bullets"] == 1
    assert resume.resume_data["sections"][0]["items"][0]["bullets"][-1].startswith("负责 VMware")


@pytest.mark.asyncio
async def test_apply_rejects_invalid_or_missing_company(monkeypatch):
    for ref in ("projects[0]", "work_experiences[9]"):
        resume = _Resume([_candidate()])
        svc, profile_loader = _make_service(resume, monkeypatch=monkeypatch)
        monkeypatch.setattr(rs.ProfileService, "profile_to_dict", lambda _self, uid: profile_loader(uid))
        with pytest.raises(Exception):
            await svc.apply_enhancements("r", "u", [{"index": 0, "target_source_ref": ref}])
        assert not svc.db.committed


@pytest.mark.asyncio
async def test_apply_deduplicates_bullets_and_indices(monkeypatch):
    candidate = _candidate("负责基础设施日常运维")
    resume = _Resume([candidate])
    _, result = await _apply(monkeypatch, resume, [
        {"index": 0, "target_source_ref": "work_experiences[0]"},
        {"index": 0, "target_source_ref": "work_experiences[0]"},
    ])
    bullets = resume.resume_data["sections"][0]["items"][0]["bullets"]
    assert bullets == ["负责基础设施日常运维"]
    assert result["applied"] == 1
    assert result["added_bullets"] == 0


@pytest.mark.asyncio
async def test_apply_rejects_empty_candidates_and_bad_status(monkeypatch):
    for resume, placements in ((_Resume([]), [{"index": 0, "target_source_ref": "work_experiences[0]"}]),
                               (_Resume([_candidate()], status="pending"), [{"index": 0, "target_source_ref": "work_experiences[0]"}])):
        svc, profile_loader = _make_service(resume, monkeypatch=monkeypatch)
        monkeypatch.setattr(rs.ProfileService, "profile_to_dict", lambda _self, uid: profile_loader(uid))
        with pytest.raises(Exception):
            await svc.apply_enhancements("r", "u", placements)


# ---------------- 版本快照：apply 也留档 ----------------
@pytest.mark.asyncio
async def test_apply_creates_version_snapshot(monkeypatch):
    resume = _Resume([_candidate()])
    svc, _ = await _apply(monkeypatch, resume, [{"index": 0, "target_source_ref": "work_experiences[0]"}])
    created = svc.version_repo.created
    # 存量简历（无任何历史）首次修改：先补一条 AI 原始基线，再记合并后的状态
    assert [c["label"] for c in created] == ["ai_generated", "enhancement_applied"]
    assert [c["version_no"] for c in created] == [1, 2]
    assert created[0]["resume_data"]["sections"][0]["items"][0]["bullets"] == ["负责基础设施日常运维"]
    # 快照存的是合并后的完整内容
    snap_item = created[1]["resume_data"]["sections"][0]["items"][0]
    assert snap_item["bullets"][-1] == "负责 Windows Server 运维"


# ---------------- 回写档案中心 ----------------
def _orm_work(company="真实公司", achievements=None, description=None):
    return SimpleNamespace(
        id=uuid.uuid4(), company=company, position="运维工程师", order_index=0, visibility=True,
        achievements=list(achievements or []), description=list(description or []),
    )


def _profile_row_with(works):
    return SimpleNamespace(id=uuid.uuid4(), work_experiences=works)


async def _apply_with_profile(monkeypatch, resume, placements, profile_row):
    """回写场景专用：先建服务（会重置桩），再注入档案行，最后执行。"""
    svc, profile_loader = _make_service(resume, monkeypatch=monkeypatch)
    monkeypatch.setattr(rs.ProfileService, "profile_to_dict", lambda _self, uid: profile_loader(uid))
    _FakeProfileRepo.profile_row = profile_row
    return svc, await svc.apply_enhancements("r", "u", placements)


@pytest.mark.asyncio
async def test_write_back_appends_to_profile_achievements(monkeypatch):
    resume = _Resume([_candidate()])
    work = _orm_work()
    svc, result = await _apply_with_profile(
        monkeypatch, resume,
        [{"index": 0, "target_source_ref": "work_experiences[0]", "write_back_profile": True}],
        _profile_row_with([work]),
    )
    assert result["written_back_to_profile"] == 1
    assert len(_FakeProfileRepo.updates) == 1
    model, entity_id, _profile_id, data = _FakeProfileRepo.updates[0]
    assert model is rs.WorkExperience and entity_id == work.id
    assert data["achievements"] == ["负责 Windows Server 运维"]


@pytest.mark.asyncio
async def test_write_back_dedups_against_existing(monkeypatch):
    # 档案里已有同一条（去空白+忽略大小写），不应重复写回
    resume = _Resume([_candidate("负责基础设施日常运维")])
    work = _orm_work(description=["负责基础设施日常运维"], achievements=["量化成果A"])
    _, result = await _apply_with_profile(
        monkeypatch, resume,
        [{"index": 0, "target_source_ref": "work_experiences[0]", "write_back_profile": True}],
        _profile_row_with([work]),
    )
    assert result["written_back_to_profile"] == 0
    assert _FakeProfileRepo.updates == []


@pytest.mark.asyncio
async def test_no_write_back_by_default(monkeypatch):
    resume = _Resume([_candidate()])
    _, result = await _apply_with_profile(
        monkeypatch, resume,
        [{"index": 0, "target_source_ref": "work_experiences[0]"}],  # 未勾选回写
        _profile_row_with([_orm_work()]),
    )
    assert result["added_bullets"] == 1
    assert result["written_back_to_profile"] == 0
    assert _FakeProfileRepo.updates == []
