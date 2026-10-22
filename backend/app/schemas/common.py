"""通用响应模型：统一 {code, message, data}。"""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: T | None = None


def success(data: Any = None, message: str = "success") -> dict:
    """路由层快捷包装统一响应。"""
    return {"code": 0, "message": message, "data": data}
