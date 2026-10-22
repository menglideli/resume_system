"""数据库连接：SQLAlchemy 2.0 异步引擎 + Session 工厂 + ORM Base。"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # SQL 回显会淹没业务日志，需要排查 SQL 时临时改 True
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""
    pass


async def get_db():
    """FastAPI 依赖：提供一个请求级的异步 Session，异常时回滚。"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
