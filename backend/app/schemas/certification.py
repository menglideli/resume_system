"""证书 Schema。"""
import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class CertificationCreate(BaseModel):
    name: str = Field(..., max_length=100)
    issuer: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    credential_id: str | None = None
    order_index: int = 0
    visibility: bool = True
    custom_fields: dict[str, Any] = {}


class CertificationUpdate(BaseModel):
    name: str | None = None
    issuer: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    credential_id: str | None = None
    order_index: int | None = None
    visibility: bool | None = None
    custom_fields: dict[str, Any] | None = None


class CertificationResponse(CertificationCreate):
    id: uuid.UUID
    profile_id: uuid.UUID

    model_config = {"from_attributes": True}
