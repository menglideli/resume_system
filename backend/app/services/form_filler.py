"""报名表填充器（指令 7 交付物）：按映射数据回填 PDF / Word / Excel。

- PDF：有 AcroForm 用 pypdf 写表单域；无表单域生成「对照填写指南」txt。
- Word：表格相邻单元格写入 + 段落下划线替换。
- Excel：按解析时记录的 cell 坐标写入。
"""
import re
from pathlib import Path
from typing import Any

from app.utils.exceptions import FileProcessException


class FormFiller:
    # ==================================================================
    # PDF
    # ==================================================================
    def fill_pdf(self, source_path: str, mapping_data: dict[str, Any], output_path: str) -> str:
        """mapping_data: {form_field_name: value}。返回输出文件路径。"""
        from pypdf import PdfReader, PdfWriter

        reader = PdfReader(source_path)
        has_form = any(
            annot.get_object().get("/FT") is not None
            for page in reader.pages
            for annot in (page.get("/Annots", []) or [])
        )
        if has_form:
            writer = PdfWriter()
            writer.append(reader)
            values = {k: str(v) for k, v in mapping_data.items() if v is not None}
            for page in writer.pages:
                writer.update_page_form_field_values(page, values, auto_regenerate=False)
            writer.set_need_appearances_writer(True)
            with open(output_path, "wb") as f:
                writer.write(f)
            return output_path

        # ---- 非表单 PDF：生成对照填写指南 ----
        guide = Path(output_path).with_suffix(".填写指南.txt")
        lines = ["报名表对照填写指南（原 PDF 无可写表单域，请按下列对照手工填写）", "=" * 60, ""]
        for field, value in mapping_data.items():
            lines.append(f"{field}：{value}")
        guide.write_text("\n".join(lines), encoding="utf-8")
        return str(guide)

    # ==================================================================
    # Word
    # ==================================================================
    def fill_word(self, source_path: str, mapping_data: dict[str, Any], output_path: str) -> str:
        from docx import Document

        doc = Document(source_path)
        replaced: set[str] = set()

        # ---- 1) 表格：标签单元格右侧空格写入 ----
        for table in doc.tables:
            for row in table.rows:
                cells = row.cells
                for i in range(len(cells) - 1):
                    label = cells[i].text.strip().rstrip("：:")
                    if label in mapping_data and not cells[i + 1].text.strip():
                        cells[i + 1].text = str(mapping_data[label])
                        replaced.add(label)

        # ---- 2) 段落：下划线替换为值 ----
        blank_re = re.compile(r"([一-龥A-Za-z（）()·]{1,15})\s*[:：]?\s*(?:_{3,}|＿{2,})")
        for para in doc.paragraphs:
            text = para.text
            for match in blank_re.finditer(text):
                label = match.group(1).strip(" ：:")
                if label in mapping_data and label not in replaced:
                    new_text = text[: match.start()] + f"{label}：{mapping_data[label]}" + text[match.end():]
                    for run in para.runs:
                        run.text = ""
                    para.runs[0].text = new_text if para.runs else para.add_run(new_text)
                    replaced.add(label)
                    break

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)
        return output_path

    # ==================================================================
    # Excel
    # ==================================================================
    def fill_excel(self, source_path: str, mapping_data: dict[str, Any], output_path: str) -> str:
        from openpyxl import load_workbook

        wb = load_workbook(source_path)
        # 扫描「标签-空格」对并写入（与解析器逻辑对称）
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for i, cell in enumerate(row[:-1]):
                    label = str(cell.value).strip().rstrip("：:") if cell.value is not None else ""
                    if label in mapping_data and row[i + 1].value in (None, ""):
                        row[i + 1].value = str(mapping_data[label])
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        wb.save(output_path)
        return output_path

    # ------------------------------------------------------------------
    def fill(self, file_type: str, source_path: str, mapping_data: dict[str, Any], output_path: str) -> str:
        if file_type == "pdf":
            return self.fill_pdf(source_path, mapping_data, output_path)
        if file_type == "word":
            return self.fill_word(source_path, mapping_data, output_path)
        if file_type == "excel":
            return self.fill_excel(source_path, mapping_data, output_path)
        raise FileProcessException(f"不支持的文件类型: {file_type}")


form_filler = FormFiller()
