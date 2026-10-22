"""后台生成任务回归测试：不依赖数据库与外部 API。

钉住几个踩过的坑：
  - 时间比较：MySQL DATETIME 取回来可能是 naive（本地时间），也可能是 aware，
    混着比会差 8 小时，导致孤儿任务判定永远不触发或立刻误触发。
  - 超时链条：外层任务总超时必须大于单次 AI 调用的上限，否则每次慢调用都撞外层超时。
  - 巡检只能回收「本进程没在跑」的任务，正在跑的必须在 _RUNNING 里被豁免。
"""
from datetime import datetime, timedelta, timezone

from app.services import resume_service as rs
from app.services.resume_service import GEN_TIMEOUT, STALE_AFTER, _as_local_naive


def test_naive_datetime_passes_through():
    """MySQL DATETIME 常见的 naive 值：按本地时间原样返回。"""
    dt = datetime(2026, 9, 1, 12, 0, 0)
    assert _as_local_naive(dt) == dt


def test_aware_datetime_converted_to_local_naive():
    """带时区的值：换算成本地 naive，避免与 naive 的 created_at 混比时差 8 小时。"""
    utc = datetime(2026, 9, 1, 4, 0, 0, tzinfo=timezone.utc)
    local = _as_local_naive(utc)
    assert local.tzinfo is None
    # 换算后仍代表同一时刻
    assert local == utc.astimezone().replace(tzinfo=None)


def test_none_survives():
    assert _as_local_naive(None) is None


def test_outer_timeout_exceeds_single_ai_call():
    """外层任务总超时必须大于单次 AI 调用的推理模型下限（600s）。

    否则一次正常的慢调用还没返回就被外层 wait_for 砍断，用户只会看到「生成超时」。
    """
    assert GEN_TIMEOUT > 600


def test_running_registry_is_module_level():
    """_RUNNING 必须是模块级字典（跨实例共享），巡检靠它豁免正在跑的任务。"""
    assert isinstance(rs._RUNNING, dict)
    rs._RUNNING["__probe__"] = 1.0
    try:
        assert "__probe__" in rs._RUNNING
    finally:
        rs._RUNNING.pop("__probe__", None)


def test_stale_threshold_is_sane():
    """判定阈值要比任务总超时短，否则任务还在跑就被判孤儿（虽然 _RUNNING 会豁免）。"""
    assert 0 < STALE_AFTER <= GEN_TIMEOUT


def test_reap_and_watchdog_are_coroutines():
    import inspect

    assert inspect.iscoroutinefunction(rs.reap_stale_pending)
    assert inspect.iscoroutinefunction(rs.watchdog)


def test_retry_reuses_the_original_preferences():
    """重试必须用当初的参数重跑，不能退化成 {}。

    否则用户最初选的 management 模板 / 2 页 / 英文，重试后全变成默认值，
    拿到一份跟自己预期完全不符的简历。
    """
    from tests.helpers import accessed_names

    from app.services.resume_service import ResumeService

    names = accessed_names(ResumeService.retry)
    assert "preferences" in names, "retry 没有读取已落库的 preferences"


def test_generate_persists_preferences():
    """generate 必须把参数存下来，否则 retry 无从复用。"""
    from tests.helpers import string_consts

    from app.services.resume_service import ResumeService

    assert "preferences" in string_consts(ResumeService.generate)


def test_empty_profile_is_detected():
    """空档案要能在调用 AI 之前拦下来：白跑一轮几分钟的推理，产出必然是空壳。"""
    assert rs.is_profile_empty({})
    assert rs.is_profile_empty({"profiles": {"name": "", "summary": None}, "educations": [], "skills": []})
    # 只要有一条实质内容就不算空 —— 名字 / 技能 / 经历任一即可
    assert not rs.is_profile_empty({"profiles": {"name": "李兴良"}})
    assert not rs.is_profile_empty({"profiles": {"name": ""}, "skills": [{"name": "Rust"}]})
    assert not rs.is_profile_empty({"work_experiences": [{"company": "某公司"}]})


def test_generation_calls_the_empty_profile_guard():
    """光有 is_profile_empty 这个函数不够，生成流程必须真的调用它。

    只测纯函数的话，把调用点注释掉测试照样全绿 —— 空档案还是会白烧一轮推理。
    """
    from tests.helpers import accessed_names

    assert "is_profile_empty" in accessed_names(rs._run_generation_impl)


def test_generation_rejects_empty_result():
    """AI 回一个没有 sections 的空壳时必须判失败，不能照写 generated。

    否则用户看到「生成成功」，点进去一片空白，完全无从排查。
    """
    from tests.helpers import string_consts

    consts = string_consts(rs._run_generation_impl)
    assert "sections" in consts, "缺少对 sections 为空的校验"
    assert any("空简历" in c for c in consts), "缺少空简历的失败提示"


def test_retry_refuses_to_wipe_generated_content():
    """重试对已生成的简历必须是拒绝，而不是清空 resume_data 重跑。

    两处都不能松：
      - 状态守卫：否则一次误点（或未来的「重新生成」入口）就静默销毁已生成的内容；
      - 不清空旧字段：与面试准备同策略，生成失败时旧内容还在，成功后再覆盖。
    """
    from tests.helpers import accessed_names, string_consts

    from app.services.resume_service import ResumeService

    consts = string_consts(ResumeService.retry)
    assert "generated" in consts, "retry 缺少「已生成则拒绝」的状态守卫"
    assert "resume_data" not in consts, "retry 不应清空 resume_data —— 失败就没内容可展示了"
    assert "status" in accessed_names(ResumeService.retry)


def test_resume_fact_sanitizer_keeps_only_profile_entities():
    profile = {
        "work_experiences": [{"company": "真实公司"}],
        "projects": [{"name": "真实项目"}],
        "skills": [{"name": "Python"}],
        "educations": [{"school": "真实大学"}],
        "certifications": [],
    }
    raw = {"sections": [
        {"type": "summary", "title": "简介", "content": "针对岗位改写的摘要"},
        {"type": "experience", "title": "工作", "items": [
            {"company": "模型改坏的公司名", "source_ref": "work_experiences[0]", "relevance": 9},
            {"company": "虚构公司", "relevance": 10},
        ]},
        {"type": "skills", "title": "技能", "items": [
            {"name": "Python", "relevance": 8}, {"name": "Kubernetes", "relevance": 10},
        ]},
    ]}
    clean = rs.sanitize_resume_facts(raw, profile)
    exp = next(s for s in clean["sections"] if s["type"] == "experience")
    skills = next(s for s in clean["sections"] if s["type"] == "skills")
    assert [x["company"] for x in exp["items"]] == ["真实公司"]
    assert [x["name"] for x in skills["items"]] == ["Python"]
    assert skills["items"][0]["source_ref"] == "skills[0]"


def test_skill_category_and_level_are_restored_from_profile():
    profile = {
        "skills": [{"name": "Python", "category": "编程语言", "proficiency": 4}],
        "work_experiences": [], "projects": [], "educations": [], "certifications": [],
    }
    raw = {"sections": [{"type": "skills", "title": "技能", "items": [
        {"name": "Python", "category": "模型伪造分类", "level": "专家", "source_ref": "skills[0]", "relevance": 9},
    ]}]}
    item = rs.sanitize_resume_facts(raw, profile)["sections"][0]["items"][0]
    assert item["category"] == "编程语言"
    assert item["level"] == "熟练"


def test_rich_profile_rejects_underfilled_resume():
    profile = {"work_experiences": [
        {"description": "负责核心系统设计与交付" * 20, "achievements": []},
        {"description": "负责平台稳定性建设与优化" * 20, "achievements": []},
    ], "projects": []}
    thin = {"sections": [
        {"type": "summary", "content": "太短"},
        {"type": "experience", "items": [{"bullets": ["一条"]}]},
    ]}
    import pytest
    with pytest.raises(Exception) as exc:
        rs.validate_resume_content_budget(thin, profile)
    assert "内容过短" in str(exc.value)


def test_sparse_profile_does_not_force_fabricated_content():
    rs.validate_resume_content_budget(
        {"sections": [{"type": "summary", "content": "短但真实"}]},
        {"work_experiences": [{"description": "只有一点素材"}], "projects": []},
    )


def test_match_details_filter_invalid_evidence_and_recalculate_score():
    profile = {
        "skills": [{"name": "Python"}],
        "work_experiences": [], "projects": [], "educations": [], "certifications": [],
    }
    details = rs.sanitize_match_details([
        {"requirement": "Python", "priority": "must", "status": "direct", "evidence_refs": ["skills[0]"]},
        {"requirement": "Kubernetes", "priority": "must", "status": "direct", "evidence_refs": ["skills[99]"]},
    ], profile)
    assert details[0]["status"] == "direct"
    assert details[1]["status"] == "missing"
    assert rs.match_score_from_details(details) == 50


def test_export_filter_removes_unverified_ai_additions():
    raw = {"sections": [{"type": "projects", "items": [
        {"name": "真实原项目"},
        {"name": "未确认", "provenance": "user_confirmed_enhancement", "verified": False},
        {"name": "已确认", "provenance": "user_confirmed_enhancement", "verified": True},
    ]}]}
    safe = rs.exportable_resume_data(raw)
    assert [x["name"] for x in safe["sections"][0]["items"]] == ["真实原项目", "已确认"]
    assert safe["sections"][0]["items"][1]["relevance"] == 8


def test_reap_uses_updated_at_not_created_at():
    """重试是原地重跑已有行，created_at 停留在首次创建时间。

    拿它当 pending 起点会把刚提交的任务判成孤儿；多 worker 部署时更会误杀
    别的进程正在跑的任务（那个进程的 _RUNNING 本进程看不到）。

    断言走字节码而不是源码文本：源码注释里也写了 created_at，按文本匹配会误报。
    """
    from tests.helpers import accessed_names

    names = accessed_names(rs.reap_stale_pending)
    assert "updated_at" in names
    assert "created_at" not in names
