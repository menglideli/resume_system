"""照片库业务层：上传 / 列表 / 删除（文件存 PHOTO_DIR，文件名 UUID 化）。"""
import uuid
from pathlib import Path

import aiofiles
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.photo import Photo
from app.repositories.photo_repo import PhotoRepository
from app.utils.exceptions import BadRequestException, NotFoundException

# 允许的图片扩展名 → MIME
ALLOWED_IMAGE_EXTS = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp",
}


class PhotoService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = PhotoRepository(db)

    async def upload(self, user_id: uuid.UUID, filename: str, data: bytes, category: str) -> Photo:
        if len(data) > settings.MAX_UPLOAD_SIZE:
            raise BadRequestException(f"文件大小超过限制（{settings.MAX_UPLOAD_SIZE // 1024 // 1024}MB）")
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        mime = ALLOWED_IMAGE_EXTS.get(ext)
        if not mime:
            raise BadRequestException(f"不支持的图片格式：.{ext}（仅支持 jpg/jpeg/png/gif/webp/bmp）")
        category = (category or "").strip() or "other"

        stored = Path(settings.PHOTO_DIR) / str(user_id) / f"{uuid.uuid4().hex}.{ext}"
        stored.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(stored, "wb") as f:
            await f.write(data)

        photo = await self.repo.create({
            "user_id": user_id, "category": category,
            "original_filename": filename, "stored_path": str(stored),
            "mime_type": mime, "size": len(data),
        })
        await self.db.commit()
        return photo

    async def list(self, user_id: uuid.UUID, category: str | None = None) -> list[Photo]:
        return await self.repo.list_by_user(user_id, category)

    async def get_file(self, photo_id: uuid.UUID, user_id: uuid.UUID) -> tuple[str, str | None]:
        """返回 (文件路径, MIME)；文件丢失时报错提示重新上传。"""
        photo = await self.repo.get_by_user(photo_id, user_id)
        if photo is None:
            raise NotFoundException("照片不存在")
        if not Path(photo.stored_path).exists():
            raise NotFoundException("照片文件丢失，请删除记录后重新上传")
        return photo.stored_path, photo.mime_type

    async def delete(self, photo_id: uuid.UUID, user_id: uuid.UUID) -> None:
        photo = await self.repo.get_by_user(photo_id, user_id)
        if photo is None:
            raise NotFoundException("照片不存在")
        Path(photo.stored_path).unlink(missing_ok=True)  # 物理文件一并删除
        await self.repo.delete(photo)
        await self.db.commit()
