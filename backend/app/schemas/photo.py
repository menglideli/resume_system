"""照片 Schema。"""
import uuid
from datetime import datetime

from pydantic import BaseModel


class PhotoResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    category: str
    original_filename: str
    mime_type: str | None
    size: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
