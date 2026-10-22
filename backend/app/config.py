"""配置管理：基于 Pydantic Settings，所有配置均可被环境变量 / .env 覆盖。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 应用
    APP_NAME: str = "智能简历投递系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # 数据库 / 缓存
    DATABASE_URL: str = "mysql+asyncmy://root:root@localhost:3306/resume_system"
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET_KEY: str = "please-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # 初始管理员（首次启动自动创建，已存在则忽略）
    ADMIN_DEFAULT_PASSWORD: str = "admin123"

    # Kimi API
    KIMI_API_KEY: str = ""
    KIMI_BASE_URL: str = "https://api.moonshot.cn/v1"
    KIMI_MODEL: str = "kimi-latest"
    KIMI_TIMEOUT: int = 120          # 秒
    KIMI_MAX_TOKENS: int = 4096
    # 推理模型（kimi-k3 等）的思考强度 low/high/max。模型默认 max，生成整份简历时
    # 思考 token 会膨胀到数千，单次调用超过 500 秒被服务端/代理掐断。
    # 实测同一任务：max 130s(reasoning 2224) / high 78s(131) / low 60s(5)，
    # 而 high 的正文反而比 low 更充实，故默认 high。
    KIMI_REASONING_EFFORT: str = "high"

    # 文件存储
    UPLOAD_DIR: str = "./storage/uploads"
    EXPORT_DIR: str = "./storage/exports"
    PHOTO_DIR: str = "./storage/photos"
    MAX_UPLOAD_SIZE: int = 20 * 1024 * 1024  # 20MB

    # PDF 渲染：Playwright 浏览器路径（None = 使用 playwright 自带 chromium）
    CHROMIUM_EXECUTABLE_PATH: str | None = None

    # CORS，逗号分隔
    CORS_ORIGINS: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
