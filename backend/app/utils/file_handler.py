"""文件存储工具：本地文件系统实现（后续可平替 S3/MinIO，仅需改本模块）。"""
import uuid
from pathlib import Path

import aiofiles

from app.config import settings
from app.utils.exceptions import BadRequestException

ALLOWED_EXTENSIONS = {
    "pdf": "pdf",
    "doc": "word", "docx": "word",
    "xls": "excel", "xlsx": "excel",
}


def detect_file_type(filename: str) -> str:
    """根据扩展名识别报名表类型：pdf / word / excel。"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    file_type = ALLOWED_EXTENSIONS.get(ext)
    if not file_type:
        raise BadRequestException(f"不支持的文件格式：.{ext}（仅支持 pdf/doc/docx/xls/xlsx）")
    return file_type


async def save_upload_file(data: bytes, original_filename: str) -> tuple[str, str]:
    """保存上传文件，返回 (存储路径, 文件类型)。文件名 UUID 化防路径穿越。"""
    if len(data) > settings.MAX_UPLOAD_SIZE:
        raise BadRequestException(f"文件大小超过限制（{settings.MAX_UPLOAD_SIZE // 1024 // 1024}MB）")
    file_type = detect_file_type(original_filename)
    ext = original_filename.rsplit(".", 1)[-1].lower()
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    path = Path(settings.UPLOAD_DIR) / stored_name
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "wb") as f:
        await f.write(data)
    return str(path), file_type


def ensure_export_path(filename: str) -> str:
    """生成导出目录下的文件路径（自动建目录、文件名安全化）。"""
    safe = "".join(c if c.isalnum() or c in "._-（）()　 " else "_" for c in filename)
    path = Path(settings.EXPORT_DIR) / safe
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)
