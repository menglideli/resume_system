"""结构化简历 JSON → Jinja2 HTML → 带页数硬约束的 A4 PDF。"""
import asyncio
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pypdf import PdfReader, PdfWriter

from app.config import settings
from app.utils.exceptions import BadRequestException

logger = logging.getLogger("resume_renderer")
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
PDF_MARGIN = {"top": "15mm", "right": "15mm", "bottom": "15mm", "left": "15mm"}

_DENSITY_CSS = {
    "roomy": """
      body { font-size: 10.8pt !important; line-height: 1.62 !important; }
      .header { margin-bottom: 14px !important; padding-bottom: 12px !important; }
      .section { margin-bottom: 14px !important; }
      .section-title { margin-bottom: 8px !important; padding-bottom: 4px !important; }
      .item { margin-bottom: 10px !important; }
      ul { margin-top: 4px !important; } li { margin-bottom: 3px !important; }
    """,
    "relaxed": """
      body { font-size: 10.4pt !important; line-height: 1.55 !important; }
      .header { margin-bottom: 12px !important; padding-bottom: 10px !important; }
      .section { margin-bottom: 12px !important; }
      .section-title { margin-bottom: 7px !important; padding-bottom: 3px !important; }
      .item { margin-bottom: 8px !important; }
      ul { margin-top: 3px !important; } li { margin-bottom: 2px !important; }
    """,
    "normal": "",
    "compact": """
      body { font-size: 9.5pt !important; line-height: 1.38 !important; }
      .header { margin-bottom: 9px !important; padding-bottom: 7px !important; }
      .name { font-size: 21pt !important; }
      .section { margin-bottom: 8px !important; }
      .section-title { margin-bottom: 5px !important; padding-bottom: 2px !important; }
      .item { margin-bottom: 5px !important; }
      ul { margin: 2px 0 0 16px !important; } li { margin-bottom: 1px !important; }
    """,
    "tight": """
      @page { margin: 9mm !important; }
      body { font-size: 9pt !important; line-height: 1.25 !important; }
      .header { margin-bottom: 6px !important; padding-bottom: 5px !important; }
      .name { font-size: 19pt !important; } .target { font-size: 10pt !important; }
      .section { margin-bottom: 5px !important; }
      .section-title { font-size: 11pt !important; margin-bottom: 3px !important; padding-bottom: 1px !important; }
      .item { margin-bottom: 3px !important; }
      .item-head { font-size: 9.5pt !important; }
      .item-sub, .meta, .period, .contact, .tag, .skill-level { font-size: 9pt !important; }
      ul { margin: 1px 0 0 14px !important; padding: 0 !important; }
      li { margin-bottom: 0 !important; }
    """,
}


def prepare_resume_data(resume_data: dict[str, Any]) -> dict[str, Any]:
    """为模板准备技能分组；不改变原始 resume_data。"""
    data = deepcopy(resume_data)
    for section in data.get("sections") or []:
        if section.get("type") != "skills":
            continue
        groups: dict[str, list[dict[str, Any]]] = {}
        for item in sorted(section.get("items") or [], key=lambda x: x.get("relevance") or 0, reverse=True):
            category = str(item.get("category") or "其他技能").strip() or "其他技能"
            groups.setdefault(category, []).append(item)
        section["skill_groups"] = [
            {"category": category, "items": items, "relevance": max(i.get("relevance") or 0 for i in items)}
            for category, items in groups.items()
        ]
        section["skill_groups"].sort(key=lambda group: group["relevance"], reverse=True)
    return data


class ResumeRenderer:
    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def render_to_html(
        self, resume_data: dict[str, Any], template_name: str = "technical", density: str = "normal",
    ) -> str:
        try:
            template = self.env.get_template(f"resume_{template_name}.html")
        except Exception:
            template = self.env.get_template("resume_default.html")
        html = template.render(resume=prepare_resume_data(resume_data))
        css = _DENSITY_CSS.get(density, "")
        return html.replace("</style>", f"{css}\n</style>", 1) if css else html

    @staticmethod
    def _fit_content(resume_data: dict[str, Any], page_limit: int) -> dict[str, Any]:
        """只裁掉低相关、重复内容；不截断字符串、不伪造信息。"""
        data = deepcopy(resume_data)
        sections = data.get("sections") or []
        ranked: list[tuple[int, int, dict[str, Any]]] = []
        for si, sec in enumerate(sections):
            if sec.get("type") in {"experience", "projects"}:
                for item in sec.get("items") or []:
                    ranked.append((int(item.get("relevance") or 0), si, item))
        limit = 4 * page_limit
        selected = sorted(ranked, key=lambda x: x[0], reverse=True)[:limit]
        # 同时有工作和项目时至少各保留一项，避免单一模块挤掉全部高相关项目。
        section_kinds = {index: sections[index].get("type") for _, index, _ in ranked}
        available_kinds = {section_kinds[index] for _, index, _ in ranked}
        selected_kinds = {section_kinds[index] for _, index, _ in selected}
        for missing_kind in available_kinds - selected_kinds:
            candidate = next(
                (row for row in sorted(ranked, key=lambda x: x[0], reverse=True)
                 if section_kinds[row[1]] == missing_kind),
                None,
            )
            if candidate is not None and selected:
                selected[-1] = candidate
        keep_ids = {id(item) for _, _, item in selected}
        for sec in sections:
            kind = sec.get("type")
            if kind == "skills":
                sec["items"] = sorted(
                    sec.get("items") or [], key=lambda x: x.get("relevance") or 0, reverse=True,
                )[:10 * page_limit]
            elif kind in {"experience", "projects"}:
                items = [item for item in sec.get("items") or [] if id(item) in keep_ids]
                for item in items:
                    item["bullets"] = (item.get("bullets") or [])[:2 + min(page_limit - 1, 1)]
                sec["items"] = items
        data["sections"] = [s for s in sections if s.get("content") or s.get("items")]
        return data

    @staticmethod
    def _page_count(output_path: str) -> int:
        return len(PdfReader(output_path).pages)

    @staticmethod
    def _text_fill_ratio(output_path: str) -> float:
        """用 PDF 文本坐标估算末页纵向填充率，不把背景线条算作内容。"""
        reader = PdfReader(output_path)
        page = reader.pages[-1]
        ys: list[float] = []

        def visitor(text, cm, tm, font_dict, font_size):
            if text and text.strip():
                ys.append(float(tm[5]))

        page.extract_text(visitor_text=visitor)
        if len(ys) < 2:
            return 0.0
        page_height = float(page.mediabox.height)
        return min(1.0, max(ys) - min(ys)) / page_height

    @staticmethod
    def _write_metadata(output_path: Path, resume_data: dict[str, Any]) -> None:
        reader = PdfReader(str(output_path))
        writer = PdfWriter()
        writer.clone_document_from_reader(reader)
        header = resume_data.get("header") or {}
        name = str(header.get("name") or "候选人")
        title = str(header.get("title") or "求职简历")
        writer.add_metadata({
            "/Title": f"{name} - {title}",
            "/Author": name,
            "/Creator": "智能简历投递系统",
            "/Subject": "求职简历",
        })
        metadata_path = output_path.with_suffix(".metadata.pdf")
        with metadata_path.open("wb") as stream:
            writer.write(stream)
        metadata_path.replace(output_path)

    async def render_to_pdf(
        self,
        resume_data: dict[str, Any],
        template_name: str,
        output_path: str,
        page_limit: int = 1,
    ) -> str:
        """渲染并验收 PDF；最终页数不得超过 page_limit。"""
        page_limit = max(1, min(int(page_limit or 1), 5))
        final_path = Path(output_path)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        work_path = final_path.with_name(f".{final_path.stem}.rendering.pdf")
        work_path.unlink(missing_ok=True)
        best_path = final_path.with_name(f".{final_path.stem}.best.pdf")
        best_path.unlink(missing_ok=True)
        best: tuple[float, str, dict[str, Any], int, float] | None = None
        actual_pages = 0

        async def try_attempts(content: dict[str, Any], densities: tuple[str, ...], cropped: bool) -> bool:
            nonlocal best, actual_pages
            target_fill = 0.82 if page_limit == 1 else 0.62
            for density in densities:
                html = self.render_to_html(content, template_name, density)
                try:
                    await self._pdf_via_playwright(html, str(work_path))
                except Exception as exc:
                    logger.warning("Playwright 导出失败，降级 WeasyPrint: %s", exc)
                    await asyncio.to_thread(self._pdf_via_weasyprint, html, str(work_path))
                actual_pages = self._page_count(str(work_path))
                fill_ratio = self._text_fill_ratio(str(work_path)) if actual_pages <= page_limit else 1.0
                logger.info(
                    "PDF 版式验收：density=%s pages=%s/%s fill=%.1f%% cropped=%s",
                    density, actual_pages, page_limit, fill_ratio * 100, cropped,
                )
                if actual_pages > page_limit:
                    continue
                # 完整内容优先；同一层级选最接近目标填充率的档位。
                score = abs(fill_ratio - target_fill)
                if best is None or score < best[0]:
                    work_path.replace(best_path)
                    best = (score, density, content, actual_pages, fill_ratio)
            return best is not None

        complete_fit = await try_attempts(
            resume_data, ("roomy", "relaxed", "normal", "compact", "tight"), cropped=False,
        )
        if not complete_fit:
            fitted = self._fit_content(resume_data, page_limit)
            await try_attempts(fitted, ("normal", "compact", "tight"), cropped=True)

        work_path.unlink(missing_ok=True)
        if best is not None:
            _, density, content, actual_pages, fill_ratio = best
            self._write_metadata(best_path, content)
            best_path.replace(final_path)
            logger.info("PDF 最终版式：density=%s pages=%s fill=%.1f%%", density, actual_pages, fill_ratio * 100)
            return output_path
        best_path.unlink(missing_ok=True)
        raise BadRequestException(
            f"当前内容压缩后仍有 {actual_pages} 页，超过目标 {page_limit} 页。"
            f"请减少低相关经历，或把页数限制调整为 {actual_pages} 页后重新生成"
        )

    async def _pdf_via_playwright(self, html: str, output_path: str) -> None:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            launch_kwargs: dict[str, Any] = {"args": ["--no-sandbox", "--disable-dev-shm-usage"]}
            if settings.CHROMIUM_EXECUTABLE_PATH:
                launch_kwargs["executable_path"] = settings.CHROMIUM_EXECUTABLE_PATH
            browser = await p.chromium.launch(**launch_kwargs)
            try:
                page = await browser.new_page()
                await page.set_content(html, wait_until="networkidle")
                await page.pdf(
                    path=output_path,
                    format="A4",
                    margin=PDF_MARGIN,
                    print_background=True,
                    prefer_css_page_size=True,
                )
            finally:
                await browser.close()

    def _pdf_via_weasyprint(self, html: str, output_path: str) -> None:
        from weasyprint import HTML

        HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf(output_path)


def version_name_to_filename(version_name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "._-（）() " else "_" for c in version_name).strip()
    return f"{safe or 'resume'}.pdf"


resume_renderer = ResumeRenderer()
