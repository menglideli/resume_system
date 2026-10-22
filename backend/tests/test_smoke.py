"""冒烟测试：应用创建 + 健康检查 + 渲染引擎 + 运行时配置（不依赖数据库/外部 API）。"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.services.config_service import KEY_MASK, ConfigService
from app.services.resume_renderer import resume_renderer
from app.schemas.resume import ResumeExportRequest, ResumePreferences


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "ok"


@pytest.mark.parametrize("template", ["default", "technical", "management", "compact"])
def test_render_to_html(template):
    html = resume_renderer.render_to_html(SAMPLE_RESUME, template)
    for expected in ("张三", "个人总结", "专业技能", "工作经历", "项目经历", "教育经历", "证书与奖项"):
        assert expected in html


@pytest.mark.parametrize("template", ["default", "technical", "management", "compact"])
def test_resume_template_schema_accepts_supported_styles(template):
    assert ResumePreferences(template=template).template == template
    assert ResumeExportRequest(template=template).template == template


def test_resume_template_schema_rejects_unknown_style():
    with pytest.raises(Exception):
        ResumePreferences(template="../../other")
    with pytest.raises(Exception):
        ResumeExportRequest(template="pretty-but-unknown")


class _FakeRow:
    def __init__(self, value: str):
        self.value = value


class _NullSession:
    """伪 AsyncSession：system_config 永远为空，验证回退 .env 逻辑。"""

    async def get(self, model, key):
        return None

    async def flush(self):
        pass

    async def commit(self):
        pass


@pytest.mark.asyncio
async def test_kimi_config_fallback_to_env():
    """DB 无配置时逐键回退 .env，整数字段强转。"""
    cfg = await ConfigService(_NullSession()).get_effective_kimi_config()
    assert cfg["KIMI_API_KEY"] == settings.KIMI_API_KEY
    assert cfg["KIMI_BASE_URL"] == settings.KIMI_BASE_URL
    assert cfg["KIMI_MODEL"] == settings.KIMI_MODEL
    assert cfg["KIMI_TIMEOUT"] == int(settings.KIMI_TIMEOUT)
    assert cfg["KIMI_MAX_TOKENS"] == int(settings.KIMI_MAX_TOKENS)


@pytest.mark.asyncio
async def test_kimi_config_mask_and_keep():
    """API Key 掩码展示；掩码占位值提交时保持原值。"""
    session = _NullSession()
    store: dict[str, _FakeRow] = {}

    async def _get(model, key):
        return store.get(key)

    async def _add(obj):
        store[obj.key] = obj

    async def _set(key, value):
        row = store.get(key) or _FakeRow("")
        row.value = value
        store[key] = row

    session.get = _get
    session.add = _add
    svc = ConfigService(session)
    svc.set = _set  # 绕开 db.add/db.get，直接操作内存 store

    store["KIMI_API_KEY"] = _FakeRow("sk-real-key-1234")
    masked = await svc.get_kimi_config_masked()
    assert masked["KIMI_API_KEY"] == f"{KEY_MASK}1234"

    await svc.update_kimi_config({"KIMI_API_KEY": f"{KEY_MASK}1234", "KIMI_MODEL": "kimi-k2"})
    assert store["KIMI_API_KEY"].value == "sk-real-key-1234"  # 掩码 → 不改
    assert store["KIMI_MODEL"].value == "kimi-k2"

    with pytest.raises(Exception) as exc_info:
        await svc.update_kimi_config({"KIMI_TIMEOUT": "not-an-int"})
    assert "必须为整数" in str(exc_info.value)


SAMPLE_RESUME = {
    "header": {"name": "张三", "title": "后端开发工程师",
               "contact": {"phone": "13800001111", "email": "zhangsan@example.com"}},
    "sections": [
        {"type": "summary", "title": "个人总结", "content": "3年后端开发经验。"},
        {"type": "skills", "title": "专业技能",
         "items": [{"name": "Go", "level": "精通", "relevance": 10}]},
        {"type": "experience", "title": "工作经历",
         "items": [{"company": "XX科技", "position": "后端开发", "period": "2023.06 - 至今",
                    "bullets": ["设计并实现高并发订单系统，QPS 从 1k 提升到 5k"]}]},
        {"type": "projects", "title": "项目经历",
         "items": [{"name": "订单平台", "role": "核心开发", "period": "2024.01 - 2024.06",
                    "tech_stack": ["Go", "Redis"], "bullets": ["负责核心服务设计与交付"]}]},
        {"type": "education", "title": "教育经历",
         "items": [{"school": "示例大学", "major": "计算机科学", "degree": "本科", "period": "2018 - 2022"}]},
        {"type": "certifications", "title": "证书与奖项",
         "items": [{"name": "云计算认证", "issuer": "示例机构", "date": "2024.03"}]},
    ],
}
