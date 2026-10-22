"""FastAPI 应用入口：路由注册、全局异常处理、CORS、统一响应格式。"""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import admin, application, auth, form, jd, photo, profile, resume
from app.schemas.common import ApiResponse
from app.utils.exceptions import AppException

logger = logging.getLogger("main")


def _configure_logging() -> None:
    """让业务模块的 INFO 日志也能打到控制台。

    uvicorn 默认只给 `uvicorn.*` 配了 handler，业务 logger（resume_service / ai_service）
    因为没有 handler 会落到 lastResort —— 只显示 WARNING 及以上。结果是耗时数分钟的
    AI 生成任务在控制台上「静默」，看不到提交、耗时、token 用量的进度，只能看到最后那句报错。
    """
    try:  # 应用先于 uvicorn 配置日志被导入，此时补一个 root logger 条目即可生效
        from uvicorn.config import LOGGING_CONFIG
        LOGGING_CONFIG.setdefault("loggers", {}).setdefault(
            "", {"handlers": ["default"], "level": "INFO"}
        )
    except Exception:  # 非 uvicorn 启动（gunicorn / IDE）时走下面的兜底
        pass

    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)-8s %(name)s | %(message)s"))
        root.addHandler(handler)
    if root.level == logging.NOTSET or root.level > logging.INFO:
        root.setLevel(logging.INFO)


_configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时确保存储目录存在，并播种初始管理员 / 配置。"""
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.EXPORT_DIR).mkdir(parents=True, exist_ok=True)
    try:
        from app.services.admin_service import seed_initial_data
        await seed_initial_data()
    except Exception as exc:  # 数据库未就绪等情况下不阻断启动
        logger.warning("初始数据播种跳过: %s", exc)
    try:
        from app.services.resume_service import sweep_stale_pending
        n = await sweep_stale_pending()
        if n:
            logger.info("启动清扫：%s 个孤儿生成任务已置为失败", n)
    except Exception as exc:
        logger.warning("孤儿任务清扫跳过: %s", exc)

    # 常驻巡检：运行期持续回收孤儿 pending 任务，不再依赖“重启才清扫”
    watchdog_task = None
    try:
        from app.services.resume_service import watchdog
        watchdog_task = asyncio.create_task(watchdog())
    except Exception as exc:
        logger.warning("生成任务巡检启动失败: %s", exc)

    yield

    if watchdog_task is not None:
        watchdog_task.cancel()
        try:
            await watchdog_task
        except asyncio.CancelledError:
            pass
        except Exception:  # 巡检协程自身的异常不该影响关停流程
            pass


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ---------- CORS ----------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------- 全局异常处理：统一 {code, message, data} ----------
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.http_status,
            content={"code": exc.code, "message": exc.message, "data": None},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"code": 42200, "message": f"参数校验失败: {exc.errors()[:3]}", "data": None},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"code": 50000, "message": f"服务器内部错误: {exc}", "data": None},
        )

    # ---------- 路由注册 ----------
    prefix = settings.API_V1_PREFIX
    app.include_router(auth.router, prefix=prefix)
    app.include_router(profile.router, prefix=prefix)
    app.include_router(jd.router, prefix=prefix)
    app.include_router(resume.router, prefix=prefix)
    app.include_router(form.router, prefix=prefix)
    app.include_router(application.router, prefix=prefix)
    app.include_router(photo.router, prefix=prefix)
    app.include_router(admin.router, prefix=prefix)

    # ---------- 健康检查 ----------
    @app.get("/health", response_model=ApiResponse, tags=["系统"])
    async def health():
        return ApiResponse(data={"status": "ok", "version": settings.APP_VERSION})

    return app


app = create_app()
