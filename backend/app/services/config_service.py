"""系统运行时配置业务层：system_config 表优先，回退 .env（app.config.settings）。"""
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.system_config import SystemConfig
from app.utils.exceptions import BadRequestException

# 可在后台管理的配置键
KIMI_KEYS = ["KIMI_API_KEY", "KIMI_BASE_URL", "KIMI_MODEL", "KIMI_TIMEOUT", "KIMI_MAX_TOKENS",
             "KIMI_REASONING_EFFORT"]
INT_KEYS = {"KIMI_TIMEOUT", "KIMI_MAX_TOKENS"}
# 思考强度只能在三档里选，写错就静默退化成 high（不阻断业务）
EFFORT_KEYS = {"KIMI_REASONING_EFFORT"}
VALID_EFFORTS = {"low", "high", "max"}
KEY_MASK = "******"


class ConfigService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, key: str) -> str | None:
        obj = await self.db.get(SystemConfig, key)
        return obj.value if obj is not None else None

    async def set(self, key: str, value: str) -> None:
        obj = await self.db.get(SystemConfig, key)
        if obj is None:
            self.db.add(SystemConfig(key=key, value=value))
        else:
            obj.value = value
        await self.db.flush()

    async def get_effective_kimi_config(self) -> dict[str, Any]:
        """逐键取生效配置：system_config 非空优先，否则回退 .env。"""
        env_defaults = {
            "KIMI_API_KEY": settings.KIMI_API_KEY,
            "KIMI_BASE_URL": settings.KIMI_BASE_URL,
            "KIMI_MODEL": settings.KIMI_MODEL,
            "KIMI_TIMEOUT": settings.KIMI_TIMEOUT,
            "KIMI_MAX_TOKENS": settings.KIMI_MAX_TOKENS,
            "KIMI_REASONING_EFFORT": settings.KIMI_REASONING_EFFORT,
        }
        result: dict[str, Any] = {}
        for key, default in env_defaults.items():
            db_value = await self.get(key)
            result[key] = db_value if db_value else default
        for key in INT_KEYS:
            try:
                result[key] = int(result[key])
            except (TypeError, ValueError):
                result[key] = env_defaults[key]
        return result

    async def get_kimi_config_masked(self) -> dict[str, Any]:
        """后台管理面板展示用：API Key 掩码（仅回显后 4 位）；全部值统一转字符串，便于前端直接回显/提交。"""
        cfg = await self.get_effective_kimi_config()
        key = str(cfg.get("KIMI_API_KEY") or "")
        cfg["KIMI_API_KEY"] = f"{KEY_MASK}{key[-4:]}" if key else ""
        for k in ("KIMI_BASE_URL", "KIMI_MODEL", "KIMI_TIMEOUT", "KIMI_MAX_TOKENS",
                  "KIMI_REASONING_EFFORT"):
            cfg[k] = str(cfg.get(k) or "")
        return cfg

    async def update_kimi_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """更新配置；掩码占位值视为保持原值。"""
        for key in KIMI_KEYS:
            if data.get(key) is None:
                continue
            value = str(data[key]).strip()
            if key == "KIMI_API_KEY" and value.startswith(KEY_MASK):
                continue  # 掩码占位 → 不改
            if key in INT_KEYS and value:
                try:
                    int(value)
                except ValueError:
                    raise BadRequestException(f"{key} 必须为整数")
            if key in EFFORT_KEYS and value:
                if value.lower() not in VALID_EFFORTS:
                    raise BadRequestException(f"{key} 只能是 low / high / max")
                value = value.lower()
            await self.set(key, value)
        await self.db.commit()
        return await self.get_kimi_config_masked()
