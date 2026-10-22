"""投递记录 Repository：CRUD + 筛选列表 + 统计 + 跟进。"""
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.repositories.base import BaseRepository


class ApplicationRepository(BaseRepository[Application]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Application)

    async def get_by_user(self, app_id: uuid.UUID, user_id: uuid.UUID) -> Application | None:
        stmt = select(Application).where(Application.id == app_id, Application.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        status: str | None = None,
        channel: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[int, list[Application]]:
        stmt = select(Application).where(Application.user_id == user_id)
        count_stmt = select(func.count(Application.id)).where(Application.user_id == user_id)
        for condition in (
            Application.status == status if status else None,
            Application.channel == channel if channel else None,
            Application.applied_at >= datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc) if date_from else None,
            Application.applied_at <= datetime.combine(date_to, datetime.max.time(), tzinfo=timezone.utc) if date_to else None,
        ):
            if condition is not None:
                stmt = stmt.where(condition)
                count_stmt = count_stmt.where(condition)
        total = (await self.db.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(Application.applied_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return total, list(result.scalars().all())

    async def count_group_by(self, user_id: uuid.UUID, column) -> dict[str, int]:
        stmt = (
            select(column, func.count(Application.id))
            .where(Application.user_id == user_id)
            .group_by(column)
        )
        result = await self.db.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def count_recent(self, user_id: uuid.UUID, days: int = 7) -> int:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = select(func.count(Application.id)).where(
            Application.user_id == user_id, Application.applied_at >= since
        )
        return (await self.db.execute(stmt)).scalar_one()

    async def count_by_day(self, user_id: uuid.UUID, days: int = 30) -> dict[str, int]:
        """近 N 天每日投递量，key 为日期字符串 YYYY-MM-DD（按 applied_at 的日期分桶）。"""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(func.date(Application.applied_at), func.count(Application.id))
            .where(Application.user_id == user_id, Application.applied_at >= since)
            .group_by(func.date(Application.applied_at))
        )
        result = await self.db.execute(stmt)
        return {str(row[0]): row[1] for row in result.all()}

    async def list_follow_ups(self, user_id: uuid.UUID) -> list[Application]:
        """需要跟进：follow_up_date <= 今天 且状态不是 offer/rejected。"""
        today = date.today()
        stmt = (
            select(Application)
            .where(
                Application.user_id == user_id,
                Application.follow_up_date.is_not(None),
                Application.follow_up_date <= today,
                Application.status.notin_(["offer", "rejected"]),
            )
            .order_by(Application.follow_up_date.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
