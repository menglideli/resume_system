"""面试准备后台任务回归测试：不依赖数据库与外部 API。

钉住的点：
  - 结构性：静态方法被误置到模块级会截断类体（语法仍合法、import 仍成功、
    ast 仍通过，但方法全部变成别的函数的嵌套函数）→ 必须实际 getattr 校验。
  - 超时链条：三段 AI 串行，外层总超时必须覆盖得住。
  - 幂等：同一简历并发提交不能起两个任务重复烧 token。
  - 孤儿判定用 updated_at 而不是 created_at（重新生成时行已存在，created_at 不变）。
"""
import inspect

from app.services import interview_service as isv
from app.services.interview_service import (
    PREP_STALE_AFTER,
    PREP_TIMEOUT,
    InterviewService,
    reap_stale_preps,
)

# 三段 AI 串行调用，缺一个前台就渲染不出来
REQUIRED_METHODS = ("get", "prepare")


def test_service_methods_not_truncated():
    """见过一次真实事故：模块级 def 缩进写错把类体截断，getattr 是唯一可靠的护栏。"""
    for name in REQUIRED_METHODS:
        assert callable(getattr(InterviewService, name, None)), f"InterviewService 缺少方法 {name}"


def test_helpers_live_at_module_level():
    """巡检函数必须是模块级协程：watchdog 在 lifespan 里直接按模块名调用。"""
    assert inspect.iscoroutinefunction(reap_stale_preps)
    assert isinstance(isv._RUNNING, dict)
    assert isinstance(isv._BG_TASKS, set)


def test_prep_timeout_covers_three_ai_calls():
    """岗位调研 + 提纲 + 题库串行，单段实测就能到 2–4 分钟。"""
    assert PREP_TIMEOUT >= 600
    assert 0 < PREP_STALE_AFTER <= PREP_TIMEOUT


def test_running_registry_is_shared():
    isv._RUNNING["__probe__"] = 1.0
    try:
        assert "__probe__" in isv._RUNNING
    finally:
        isv._RUNNING.pop("__probe__", None)


def test_reap_uses_updated_at_not_created_at():
    """重新生成走 update 已有行，created_at 停留在首次创建时间。

    拿 created_at 当 pending 起点，会把刚提交的任务当成跑了很久的孤儿；
    多 worker 部署时更会误杀别的进程正在跑的任务。
    """
    from tests.helpers import accessed_names

    # 走字节码：源码注释里也写了 created_at，按源码文本匹配会误报
    names = accessed_names(reap_stale_preps)
    assert "updated_at" in names
    assert "created_at" not in names


def test_prepare_is_idempotent_against_running_task():
    """prepare 在提交任务前必须检查 _RUNNING，否则重复点击会起两个协程写同一行。"""
    src = inspect.getsource(InterviewService.prepare)
    assert "_RUNNING" in src
