"""报名表解析器（指令 7 交付物）：PDF / Word / Excel → 统一 FormStructure。

- PDF：pypdf 读 AcroForm 表单域；无表单域时用 pdfplumber 提取「标签：____」与表格；
        文本极少判定为扫描件，走 OCR（paddleocr 懒加载，未安装则提示）。
- Word：python-docx 解析表格相邻单元格 + 段落下划线填空。
- Excel：openpyxl 识别「标签-空格」相邻单元格对。
"""
import re
from pathlib import Path
from typing import Any

from app.schemas.form import FormField, FormStructure
from app.utils.exceptions import FileProcessException

# 匹配「标签：______」式填空（下划线≥3，或全角空格留白）
BLANK_RE = re.compile(r"([一-龥A-Za-z（）()·]{1,15})\s*[:：]?\s*(?:_{3,}|＿{2,}|…{2,})")
LABEL_VALUE_RE = re.compile(r"^([一-龥A-Za-z（）()·]{1,15})\s*[:：]\s*(.+)$")


class FormParser:
    # ==================================================================
    # PDF
    # ==================================================================
    def parse_pdf(self, file_path: str) -> FormStructure:
        path = Path(file_path)
        if not path.exists():
            raise FileProcessException(f"文件不存在: {file_path}")

        fields: list[FormField] = []
        raw_text = ""

        # ---- 1) AcroForm 表单域 ----
        acro_fields = self._pdf_acro_fields(file_path)
        fields.extend(acro_fields)

        # ---- 2) pdfplumber 文本/表格提取 ----
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            for page_no, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                raw_text += text + "\n"
                if not acro_fields:  # 无表单域时才用文本推断
                    fields.extend(self._fields_from_text(text, page=page_no))
                    fields.extend(self._fields_from_tables(page.extract_tables(), page=page_no))

        # ---- 3) 扫描件 OCR 兜底 ----
        if not fields and len(raw_text.strip()) < 20:
            ocr_text = self._ocr_pdf(file_path)
            raw_text = ocr_text
            fields.extend(self._fields_from_text(ocr_text, page=None))

        # 去重（同名字段保留首个）
        fields = self._dedup(fields)
        return FormStructure(
            source_file=path.name, file_type="pdf", fields=fields,
            field_count=len(fields), raw_text_preview=raw_text[:500],
            meta={"acro_form": bool(acro_fields)},
        )

    def _pdf_acro_fields(self, file_path: str) -> list[FormField]:
        from pypdf import PdfReader

        type_map = {"/Tx": "text", "/Btn": "checkbox", "/Ch": "select", "/Sig": "text"}
        result: list[FormField] = []
        try:
            reader = PdfReader(file_path)
            for page_no, page in enumerate(reader.pages, start=1):
                for annot in page.get("/Annots", []) or []:
                    obj = annot.get_object()
                    if obj.get("/FT") is None:
                        continue
                    name = str(obj.get("/T", "")).strip()
                    if not name:
                        continue
                    rect = obj.get("/Rect")
                    bbox = [float(x) for x in rect] if rect else None
                    result.append(FormField(
                        field_name=name,
                        field_type=type_map.get(str(obj.get("/FT")), "text"),
                        bbox=bbox, page=page_no,
                        value=str(obj.get("/V")) if obj.get("/V") else None,
                    ))
        except Exception:
            return []
        return result

    def _fields_from_text(self, text: str, page: int | None) -> list[FormField]:
        fields: list[FormField] = []
        for line in text.splitlines():
            for match in BLANK_RE.finditer(line):
                label = match.group(1).strip(" ：:")
                if label:
                    fields.append(FormField(field_name=label, field_type="text", page=page))
        return fields

    def _fields_from_tables(self, tables: list[list[list[Any]]], page: int | None) -> list[FormField]:
        """表格中「标签 | 空格」相邻对 → 可填字段。"""
        fields: list[FormField] = []
        for table in tables or []:
            for row in table or []:
                cells = [(c or "").strip() for c in (row or [])]
                for i in range(len(cells) - 1):
                    label, value = cells[i], cells[i + 1]
                    if label and not value and 1 <= len(label) <= 12 and "：" not in label[:-1]:
                        fields.append(FormField(field_name=label.rstrip("：:"), field_type="text", page=page))
        return fields

    def _ocr_pdf(self, file_path: str) -> str:
        """扫描件 OCR（paddleocr 懒加载）。"""
        try:
            from paddleocr import PaddleOCR  # noqa
        except ImportError as exc:
            raise FileProcessException(
                "该 PDF 疑似扫描件，需要 OCR 支持：请安装 paddleocr 后重试（pip install paddleocr paddlepaddle）"
            ) from exc
        ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        texts: list[str] = []
        for page_result in ocr.ocr(file_path, cls=True):
            for line in page_result or []:
                texts.append(line[1][0])
        return "\n".join(texts)

    # ==================================================================
    # Word
    # ==================================================================
    def parse_word(self, file_path: str) -> FormStructure:
        from docx import Document

        path = Path(file_path)
        if not path.exists():
            raise FileProcessException(f"文件不存在: {file_path}")
        doc = Document(file_path)

        fields: list[FormField] = []
        raw_parts: list[str] = []

        # ---- 1) 表格：标签-空格相邻单元格 ----
        for t_idx, table in enumerate(doc.tables):
            for r_idx, row in enumerate(table.rows):
                cells = [c.text.strip() for c in row.cells]
                raw_parts.append(" | ".join(cells))
                for i in range(len(cells) - 1):
                    label, value = cells[i].rstrip("：:"), cells[i + 1]
                    if label and not value and 1 <= len(label) <= 12:
                        fields.append(FormField(
                            field_name=label, field_type="text", cell=f"T{t_idx}R{r_idx}C{i + 1}"
                        ))

        # ---- 2) 段落：下划线填空 ----
        for para in doc.paragraphs:
            raw_parts.append(para.text)
            for match in BLANK_RE.finditer(para.text):
                label = match.group(1).strip(" ：:")
                if label:
                    fields.append(FormField(field_name=label, field_type="text"))

        fields = self._dedup(fields)
        return FormStructure(
            source_file=path.name, file_type="word", fields=fields,
            field_count=len(fields), raw_text_preview="\n".join(raw_parts)[:500],
        )

    # ==================================================================
    # Excel
    # ==================================================================
    def parse_excel(self, file_path: str) -> FormStructure:
        from openpyxl import load_workbook

        path = Path(file_path)
        if not path.exists():
            raise FileProcessException(f"文件不存在: {file_path}")
        wb = load_workbook(file_path, data_only=True)

        fields: list[FormField] = []
        raw_parts: list[str] = []
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                values = [c.value for c in row]
                raw_parts.append(" | ".join(str(v) for v in values if v is not None))
                for i, cell in enumerate(row[:-1]):
                    label = str(cell.value).strip().rstrip("：:") if cell.value is not None else ""
                    nxt = row[i + 1]
                    if label and nxt.value in (None, "") and 1 <= len(label) <= 12:
                        fields.append(FormField(
                            field_name=label, field_type="text", cell=f"{ws.title}!{nxt.coordinate}"
                        ))

        fields = self._dedup(fields)
        return FormStructure(
            source_file=path.name, file_type="excel", fields=fields,
            field_count=len(fields), raw_text_preview="\n".join(raw_parts)[:500],
        )

    # ==================================================================
    @staticmethod
    def _dedup(fields: list[FormField]) -> list[FormField]:
        seen, result = set(), []
        for f in fields:
            if f.field_name not in seen:
                seen.add(f.field_name)
                result.append(f)
        return result

    # ------------------------------------------------------------------
    def parse(self, file_path: str, file_type: str) -> FormStructure:
        """按文件类型分发解析。"""
        if file_type == "pdf":
            return self.parse_pdf(file_path)
        if file_type == "word":
            return self.parse_word(file_path)
        if file_type == "excel":
            return self.parse_excel(file_path)
        raise FileProcessException(f"不支持的文件类型: {file_type}")


form_parser = FormParser()
