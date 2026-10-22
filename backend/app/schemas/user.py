"""用户/认证相关 Schema。"""
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=64)


class UserLogin(BaseModel):
    username: str           # 支持用户名或邮箱
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    is_admin: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_admin: bool = False
