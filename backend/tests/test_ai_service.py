"""AI 服务回归测试：不依赖数据库与外部 API。

重点守住两个曾经真实发生过的事故：
  1. 类体被模块级函数截断 —— 某个方法不小心缩进到模块级函数里，类上就找不到该方法，
     语法完全合法、import 也不报错，只有真正调用时才 AttributeError。
  2. 每次调用都新建 AsyncOpenAI 客户端且从不关闭 —— 长跑后连接池/句柄耗尽，
     表现为莫名其妙的 "Connection error."。
"""
import inspect

import httpx
import pytest
from openai import APIConnectionError

from app.services import ai_service
from app.services.ai_service import MAX_ATTEMPTS, REASONING_OUTPUT_BUDGET, AIService, AIServiceException

# 七大 AI 能力 + 内部方法，缺一个都说明类结构被破坏
EXPECTED_METHODS = [
    "resume_diagnosis", "parse_jd", "generate_resume", "map_form_fields",
    "generate_interview_qa", "job_research", "interview_outline",
    "_chat_json", "_safe_chat_json", "_parse_json",
]


def test_ai_service_exposes_all_methods():
    """类体完整性：所有方法都挂在 AIService 上，且都是协程（除 _parse_json 静态解析）。"""
    for name in EXPECTED_METHODS:
        member = getattr(AIService, name, None)
        assert member is not None, f"AIService 缺少方法 {name}"
        if name != "_parse_json":
            assert inspect.iscoroutinefunction(member), f"{name} 应为协程方法"


def test_helpers_stay_at_module_level():
    """工具函数必须是模块级的，不能掉进类里，也不能反过来把类截断。"""
    for name in ("_dumps", "_fmt_error"):
        func = getattr(ai_service, name, None)
        assert callable(func), f"模块级工具函数 {name} 丢失"
        assert not hasattr(AIService, name), f"{name} 不应成为 AIService 的成员"


def test_openai_client_is_reused():
    """同一配置下复用同一个 AsyncOpenAI 客户端，避免连接池泄漏。"""
    first, second = AIService(), AIService()
    assert first.client is second.client


def test_reasoning_model_settings():
    """推理模型：不传 temperature、超时下限 600 秒、长输出预算足够。"""
    ai = AIService({"KIMI_MODEL": "kimi-k3", "KIMI_TIMEOUT": 120, "KIMI_MAX_TOKENS": 8192})
    assert ai._is_reasoning is True
    assert ai._supports_temperature is False
    assert ai._timeout >= 600
    # 实测一次简历生成要 7336 completion tokens，预算必须明显高于原 8192 上限
    assert REASONING_OUTPUT_BUDGET >= 16384


def test_non_reasoning_model_keeps_temperature():
    """非推理模型维持原行为：可传 temperature，超时不被抬高。"""
    ai = AIService({"KIMI_MODEL": "moonshot-v1-8k", "KIMI_TIMEOUT": 120})
    assert ai._is_reasoning is False
    assert ai._supports_temperature is True
    assert ai._timeout == 120


def test_fmt_error_includes_status_code():
    """报错信息要带上 HTTP 状态码和服务端 message，便于定位 401/400。"""
    class _FakeError(Exception):
        status_code = 401
        body = {"error": {"message": "Invalid Authentication"}}
        message = "Error code: 401"

    text = ai_service._fmt_error(_FakeError())
    assert "401" in text
    assert "Invalid Authentication" in text


# ---------------------------------------------------------------- 思考强度
#
# kimi-k3 的 reasoning_effort 默认是 max。实测同一任务：
#   max 130s(reasoning 2224) / high 78s(131) / low 60s(5)
# 生成整份简历时 max 档思考 token 膨胀到数千，单次调用超过 500 秒仍未返回，
# 最后被掐断成 RemoteProtocolError: Server disconnected without sending a response。
# 所以默认必须降档，且要证明这个参数真的传到了 API（只测属性证明不了调用点用了它）。

class _FakeStream:
    """模拟 openai 的 Stream：内容分块到达，末尾块带 usage 与 finish_reason。

    openai 开了 include_usage 后，最后一个 chunk 只有 usage、没有 choices，
    这里两种形态都造出来，确保收集逻辑对两种布局都成立。
    """

    PARTS = ('{"ok": ', 'true}')

    def __aiter__(self):
        async def gen():
            for part in self.PARTS:
                delta = type("D", (), {"content": part})()
                choice = type("C", (), {"delta": delta, "finish_reason": None})()
                yield type("R", (), {"choices": [choice], "usage": None})()
            delta = type("D", (), {"content": None})()
            choice = type("C", (), {"delta": delta, "finish_reason": "stop"})()
            usage = type("U", (), {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3})()
            yield type("R", (), {"choices": [choice], "usage": usage})()
        return gen()


class _TruncatedStream(_FakeStream):
    """产出内容但永远不给 finish_reason —— 模拟流到一半连接被掐断。"""

    def __aiter__(self):
        async def gen():
            for part in self.PARTS:
                delta = type("D", (), {"content": part})()
                choice = type("C", (), {"delta": delta, "finish_reason": None})()
                yield type("R", (), {"choices": [choice], "usage": None})()
        return gen()


class _RecordingCompletions:
    """记录 create() 收到的 kwargs，并返回一个够用的假流式响应。"""

    def __init__(self, stream: _FakeStream | None = None):
        self.calls: list[dict] = []
        self.stream = stream

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.stream if self.stream is not None else _FakeStream()


def _recording(ai: AIService, stream: _FakeStream | None = None) -> _RecordingCompletions:
    """把假客户端挂上去，返回记录器。"""
    rec = _RecordingCompletions(stream)
    # base_url 要带上：中断判定要用它构造可重试异常
    ai.client = type("C", (), {
        "chat": type("H", (), {"completions": rec})(),
        "base_url": "https://api.moonshot.cn/v1",
    })()
    return rec


def test_reasoning_effort_defaults_to_high():
    """推理模型默认 high —— max 档会把简历生成拖过 500 秒。"""
    ai = AIService({"KIMI_MODEL": "kimi-k3"})
    assert ai._reasoning_effort == "high"


def test_reasoning_effort_normalizes_and_falls_back():
    """大小写归一化；非法值/空值静默回退默认档，不阻断业务。"""
    assert AIService({"KIMI_MODEL": "kimi-k3", "KIMI_REASONING_EFFORT": "MAX"})._reasoning_effort == "max"
    assert AIService({"KIMI_MODEL": "kimi-k3", "KIMI_REASONING_EFFORT": "low"})._reasoning_effort == "low"
    assert AIService({"KIMI_MODEL": "kimi-k3", "KIMI_REASONING_EFFORT": "bogus"})._reasoning_effort == "high"
    assert AIService({"KIMI_MODEL": "kimi-k3", "KIMI_REASONING_EFFORT": ""})._reasoning_effort == "high"


def test_non_reasoning_model_has_no_effort():
    """非推理模型不设置思考强度，否则 API 会 400。"""
    assert AIService({"KIMI_MODEL": "moonshot-v1-8k"})._reasoning_effort is None


def test_config_schema_covers_all_managed_keys():
    """所有可后台管理的配置键都必须在 schema 里声明。

    漏一个的后果很隐蔽：pydantic 默认忽略未声明字段，接口照样返回 200，
    但值根本没存 —— 前端看着改成功了，实际一直是默认值。
    """
    from app.schemas.admin import SystemConfigUpdate
    from app.services.config_service import KIMI_KEYS

    for key in KIMI_KEYS:
        assert key in SystemConfigUpdate.model_fields, (
            f"{key} 未在 SystemConfigUpdate 声明，更新时会被静默丢弃"
        )


@pytest.mark.asyncio
async def test_chat_json_sends_reasoning_effort_for_reasoning_model():
    """调用点必须真的把 reasoning_effort 传下去，且不能同时传 temperature。"""
    ai = AIService({"KIMI_MODEL": "kimi-k3"})
    rec = _recording(ai)
    await ai._chat_json("sys", "user")
    assert rec.calls, "_chat_json 没有发起请求"
    kwargs = rec.calls[0]
    assert kwargs.get("reasoning_effort") == "high"
    assert "temperature" not in kwargs


@pytest.mark.asyncio
async def test_chat_json_sends_temperature_for_non_reasoning_model():
    """非推理模型维持原行为：传 temperature，绝不传 reasoning_effort。"""
    ai = AIService({"KIMI_MODEL": "moonshot-v1-8k"})
    rec = _recording(ai)
    await ai._chat_json("sys", "user")
    kwargs = rec.calls[0]
    assert kwargs.get("temperature") == 0.3
    assert "reasoning_effort" not in kwargs


@pytest.mark.asyncio
async def test_chat_json_streams_to_avoid_idle_disconnect():
    """必须走流式。

    推理模型思考期间服务端一个字节都不发，非流式就是一条长时间静默的连接，
    中间链路会当成空闲连接掐断 —— 同一份真实档案实测：非流式 564.7 秒失败，
    流式 71.6 秒成功（1756 个 chunk）。改回非流式 = 恢复这个故障。
    """
    ai = AIService({"KIMI_MODEL": "kimi-k3"})
    rec = _recording(ai)
    await ai._chat_json("sys", "user")
    kwargs = rec.calls[0]
    assert kwargs.get("stream") is True, "非流式会被中间链路按空闲连接掐断"
    assert (kwargs.get("stream_options") or {}).get("include_usage") is True


@pytest.mark.asyncio
async def test_stream_collect_assembles_pieces_and_usage():
    """分块内容要拼回完整 JSON，usage / finish_reason 要从末尾块取到。"""
    ai = AIService({"KIMI_MODEL": "kimi-k3"})
    rec = _recording(ai)
    result = await ai._chat_json("sys", "user")
    assert result == {"ok": True}, "分块内容没有正确拼接"
    assert rec.calls, "没有发起请求"
    assert ai.last_usage["total_tokens"] == 3, "usage 没有从流式末尾块取到"


class _FailingCompletions:
    """每次调用都抛指定异常，用于验证错误文案。"""

    def __init__(self, exc: Exception):
        self.exc = exc
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        raise self.exc


def _failing(ai: AIService, exc: Exception) -> _FailingCompletions:
    rec = _FailingCompletions(exc)
    ai.client = type("C", (), {
        "chat": type("H", (), {"completions": rec})(),
        "base_url": "https://api.moonshot.cn/v1",
    })()
    return rec


@pytest.mark.asyncio
async def test_connection_error_message_is_actionable():
    """连接中断的报错必须说清重试次数与排查方向。

    原文的「Connection error.」对用户毫无信息量 —— 这次故障排查绕了一大圈
    （怀疑代理、怀疑连接池、怀疑 payload），如果报错里直接写明「已重试 N 次、
    不是 API Key 问题、调大超时无效」，能省掉整轮排查。
    """
    ai = AIService({"KIMI_MODEL": "kimi-k3"})
    rec = _failing(ai, APIConnectionError(
        message="Connection error.",
        request=httpx.Request("POST", "https://api.moonshot.cn/v1"),
    ))
    with pytest.raises(AIServiceException) as ei:
        await ai._safe_chat_json("sys", "user")

    msg = str(ei.value)
    assert f"重试 {MAX_ATTEMPTS} 次" in msg, f"报错没说重试次数: {msg}"
    assert rec.calls == MAX_ATTEMPTS, f"重试次数与文案不一致: {rec.calls}"
    assert "不是 API Key" in msg, f"没排除 API Key 方向: {msg}"
    assert "调大超时也无效" in msg, f"没提示调超时无效: {msg}"


@pytest.mark.asyncio
async def test_truncated_stream_is_retried_not_parsed():
    """流中途断连（没有 finish_reason）必须抛可重试错误，不能拿半截 JSON 去解析。

    半截内容走到 _parse_json 只会报 AIServiceException，而它不在重试名单里 ——
    一次网络抖动就直接变成用户可见的失败。所以这里要抛 APIConnectionError，
    交给 tenacity 重来。
    """
    ai = AIService({"KIMI_MODEL": "kimi-k3"})
    rec = _recording(ai, stream=_TruncatedStream())
    with pytest.raises(APIConnectionError):
        await ai._chat_json("sys", "user")
    assert len(rec.calls) == 3, f"应重试 3 次，实际 {len(rec.calls)} 次"
