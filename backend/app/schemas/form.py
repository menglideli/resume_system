"""报名表相关 Schema（统一的 FormStructure 数据模型定义于此）。"""
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class FormField(BaseModel):
    """报名表单个字段：解析器（pdf/word/excel）与 AI 映射的统一交换格式。"""
    field_name: str
    field_type: Literal["text", "date", "number", "checkbox", "select", "textarea"] = "text"
    label: str | None = None                       # 页面上的标签文字
    bbox: list[float] | None = None                # PDF 中的位置 [x0, y0, x1, y1]
    page: int | None = None                        # 所在页码（PDF）
    cell: str | None = None                        # Excel 单元格坐标 / Word 表格坐标
    value: str | None = None                       # 当前值（已填写时）
    options: list[str] | None = None               # select/checkbox 的可选项
    required: bool = False


class FormStructure(BaseModel):
    """统一的表单结构：三种格式解析后都归一到该模型。"""
    source_file: str
    file_type: Literal["pdf", "word", "excel"]
    fields: list[FormField] = []
    field_count: int = 0
    raw_text_preview: str = ""                     # 原文预览（供调试/AI 参考）
    meta: dict[str, Any] = {}


class FieldMappingItem(BaseModel):
    form_field: str
    profile_field: str | None = None               # 如 profiles.name / educations[0].school
    confidence: float = 0.0
    value: str | None = None


class FormMappingResult(BaseModel):
    mappings: list[FieldMappingItem] = []
    unmapped: list[str] = []                       # 无法映射的表单字段
    needs_review: list[str] = []                   # 低置信度、需人工确认


class FormMappingRequest(BaseModel):
    """用户确认/修改映射：传入即覆盖 AI 结果对应项。"""
    mappings: list[FieldMappingItem] | None = None


class FormResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    original_filename: str
    file_type: str
    form_structure: dict[str, Any] | None
    field_mapping: dict[str, Any] | None
    filled_data: dict[str, Any] | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
