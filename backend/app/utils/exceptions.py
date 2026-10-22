"""统一异常定义：所有业务异常继承 AppException，由全局处理器转为统一响应。"""
from fastapi import status


class AppException(Exception):
    """业务异常基类。code 为业务错误码，http_status 为 HTTP 状态码。"""

    def __init__(self, message: str, code: int = 40000, http_status: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.code = code
        self.http_status = http_status
        super().__init__(message)


class NotFoundException(AppException):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(message, code=40400, http_status=status.HTTP_404_NOT_FOUND)


class UnauthorizedException(AppException):
    def __init__(self, message: str = "未认证或认证已过期"):
        super().__init__(message, code=40100, http_status=status.HTTP_401_UNAUTHORIZED)


class ForbiddenException(AppException):
    def __init__(self, message: str = "无权访问该资源"):
        super().__init__(message, code=40300, http_status=status.HTTP_403_FORBIDDEN)


class BadRequestException(AppException):
    def __init__(self, message: str = "请求参数错误"):
        super().__init__(message, code=40000, http_status=status.HTTP_400_BAD_REQUEST)


class ConflictException(AppException):
    def __init__(self, message: str = "资源冲突"):
        super().__init__(message, code=40900, http_status=status.HTTP_409_CONFLICT)


class AIServiceException(AppException):
    """Kimi API 调用失败 / 响应解析失败。"""
    def __init__(self, message: str = "AI 服务异常"):
        super().__init__(message, code=50200, http_status=status.HTTP_502_BAD_GATEWAY)


class FileProcessException(AppException):
    """文件解析 / 填充失败。"""
    def __init__(self, message: str = "文件处理失败"):
        super().__init__(message, code=40010, http_status=status.HTTP_400_BAD_REQUEST)
