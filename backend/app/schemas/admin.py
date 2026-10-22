"""后台管理 Schema：用户管理 + 系统配置。"""
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class AdminUserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=64)
    is_admin: bool = False


class AdminUserUpdate(BaseModel):
    email: EmailStr | None = None
    is_admin: bool | None = None


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ResetPassword(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=64)


class SystemConfigUpdate(BaseModel):
    """Kimi 配置更新；API Key 传掩码占位值时保持原值。数字键兼容 JSON number 自动转字符串。"""
    KIMI_API_KEY: str | None = None
    KIMI_BASE_URL: str | None = None
    KIMI_MODEL: str | None = None
    KIMI_TIMEOUT: str | None = None
    KIMI_MAX_TOKENS: str | None = None
    # 不在这里声明，pydantic 会把该字段静默丢掉 —— 前端改了配置、后端返回 200，
    # 实际上什么都没存（校验逻辑也不会执行）。
    KIMI_REASONING_EFFORT: str | None = None

    @field_validator("KIMI_TIMEOUT", "KIMI_MAX_TOKENS", mode="before")
    @classmethod
    def _num_to_str(cls, v):
        if isinstance(v, (int, float)):
            return str(int(v))
        return v
