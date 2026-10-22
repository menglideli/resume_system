"""PDF 页数与双向密度适配回归测试；不启动浏览器。"""
from pathlib import Path

import pytest

from app.services.resume_renderer import ResumeRenderer, prepare_resume_data


async def _run_fake(monkeypatch, tmp_path, pages, fills):
    renderer = ResumeRenderer()
    densities: list[str] = []
    original_render = renderer.render_to_html

    def render(data, template, density="normal"):
        densities.append(density)
        return original_render(data, template, density)

    async def fake_pdf(html, output_path):
        Path(output_path).write_bytes(b"pdf")

    page_values = iter(pages)
    fill_values = iter(fills)
    monkeypatch.setattr(renderer, "render_to_html", render)
    monkeypatch.setattr(renderer, "_pdf_via_playwright", fake_pdf)
    monkeypatch.setattr(renderer, "_page_count", lambda _: next(page_values))
    monkeypatch.setattr(renderer, "_text_fill_ratio", lambda _: next(fill_values))
    monkeypatch.setattr(renderer, "_write_metadata", lambda *_: None)
    output = tmp_path / "resume.pdf"
    await renderer.render_to_pdf(
        {"header": {"name": "测试"}, "sections": []}, "technical", str(output), page_limit=1,
    )
    return densities, output


@pytest.mark.asyncio
async def test_sparse_resume_selects_roomy(monkeypatch, tmp_path):
    densities, output = await _run_fake(
        monkeypatch, tmp_path,
        pages=[1, 1, 1, 1, 1],
        fills=[0.82, 0.74, 0.65, 0.55, 0.45],
    )
    assert densities == ["roomy", "relaxed", "normal", "compact", "tight"]
    assert output.exists()


@pytest.mark.asyncio
async def test_roomy_overflows_then_relaxed_is_selected(monkeypatch, tmp_path):
    densities, output = await _run_fake(
        monkeypatch, tmp_path,
        pages=[2, 1, 1, 1, 1],
        fills=[0.82, 0.72, 0.62, 0.52],
    )
    assert densities[:2] == ["roomy", "relaxed"]
    assert output.exists()


@pytest.mark.asyncio
async def test_renderer_rejects_and_removes_over_limit_pdf(monkeypatch, tmp_path):
    renderer = ResumeRenderer()

    async def fake_pdf(html, output_path):
        Path(output_path).write_bytes(b"pdf")

    monkeypatch.setattr(renderer, "_pdf_via_playwright", fake_pdf)
    monkeypatch.setattr(renderer, "_page_count", lambda _: 2)
    output = tmp_path / "resume.pdf"
    with pytest.raises(Exception) as exc:
        await renderer.render_to_pdf({"header": {"name": "测试"}, "sections": []}, "technical", str(output), page_limit=1)
    assert "超过目标 1 页" in str(exc.value)
    assert not output.exists()


@pytest.mark.asyncio
async def test_failed_reexport_preserves_previous_pdf(monkeypatch, tmp_path):
    renderer = ResumeRenderer()

    async def fake_pdf(html, output_path):
        Path(output_path).write_bytes(b"new-over-limit")

    monkeypatch.setattr(renderer, "_pdf_via_playwright", fake_pdf)
    monkeypatch.setattr(renderer, "_page_count", lambda _: 2)
    output = tmp_path / "resume.pdf"
    output.write_bytes(b"previous-valid-pdf")
    with pytest.raises(Exception):
        await renderer.render_to_pdf(
            {"header": {"name": "测试"}, "sections": []}, "technical", str(output), page_limit=1,
        )
    assert output.read_bytes() == b"previous-valid-pdf"


def test_one_page_content_budget_keeps_high_relevance_items():
    renderer = ResumeRenderer()
    data = {"sections": [
        {"type": "skills", "items": [{"name": f"S{i}", "relevance": i} for i in range(12)]},
        {"type": "projects", "items": [
            {"name": f"P{i}", "relevance": i, "bullets": ["a", "b", "c"]} for i in range(6)
        ]},
    ]}
    fitted = renderer._fit_content(data, 1)
    skills = next(s for s in fitted["sections"] if s["type"] == "skills")["items"]
    projects = next(s for s in fitted["sections"] if s["type"] == "projects")["items"]
    assert len(skills) == 10
    assert [p["name"] for p in projects] == ["P2", "P3", "P4", "P5"]
    assert all(len(p["bullets"]) == 2 for p in projects)


def test_skill_groups_are_sorted_by_relevance():
    prepared = prepare_resume_data({"sections": [{"type": "skills", "items": [
        {"name": "Redis", "category": "数据库", "relevance": 7},
        {"name": "Python", "category": "编程语言", "relevance": 10},
        {"name": "MySQL", "category": "数据库", "relevance": 9},
        {"name": "Git", "relevance": 5},
    ]}]})
    groups = prepared["sections"][0]["skill_groups"]
    assert [group["category"] for group in groups] == ["编程语言", "数据库", "其他技能"]
    assert [item["name"] for item in groups[1]["items"]] == ["MySQL", "Redis"]
