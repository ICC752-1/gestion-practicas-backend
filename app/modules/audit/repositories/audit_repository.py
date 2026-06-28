"""Consultas de lectura sobre LogAction."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import Date, Select, and_, cast, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models.audit_log_model import AuditLog
from app.modules.audit.schemas.audit_schema import AuditEventFilters
from app.modules.auth.models.user_model import User


class AuditRepository:
    """Repositorio de auditoria transversal."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_events(
        self,
        filters: AuditEventFilters,
        *,
        limit: int,
        offset: int,
    ) -> list[tuple[AuditLog, User | None]]:
        query = (
            self._base_query(filters, AuditLog, User)
            .order_by(desc(AuditLog.timestamp), desc(AuditLog.id))
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(query)

        return [(log, actor) for log, actor in result.all()]

    async def count_events(self, filters: AuditEventFilters) -> int:
        query = self._base_query(filters, func.count(AuditLog.id))
        result = await self.db.execute(query)

        return result.scalar_one() or 0

    async def count_last_24_hours(self, filters: AuditEventFilters) -> int:
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=24)
        query = self._base_query(filters, func.count(AuditLog.id)).where(
            AuditLog.timestamp >= cutoff,
        )
        result = await self.db.execute(query)

        return result.scalar_one() or 0

    async def count_without_actor(self, filters: AuditEventFilters) -> int:
        query = self._base_query(filters, func.count(AuditLog.id)).where(
            AuditLog.user_id.is_(None),
        )
        result = await self.db.execute(query)

        return result.scalar_one() or 0

    async def count_by_action(self, filters: AuditEventFilters) -> dict[str, int]:
        query = (
            self._base_query(filters, AuditLog.action, func.count(AuditLog.id))
            .group_by(AuditLog.action)
            .order_by(AuditLog.action.asc())
        )
        result = await self.db.execute(query)

        return {self._enum_value(action): total for action, total in result.all()}

    async def get_event(self, event_id: int) -> tuple[AuditLog, User | None] | None:
        query = (
            select(AuditLog, User)
            .select_from(AuditLog)
            .outerjoin(User, User.id == AuditLog.user_id)
            .where(AuditLog.id == event_id)
        )
        result = await self.db.execute(query)

        return result.first()

    def _base_query(self, filters: AuditEventFilters, *columns) -> Select:
        query = (
            select(*columns)
            .select_from(AuditLog)
            .outerjoin(User, User.id == AuditLog.user_id)
        )
        conditions = self._conditions(filters)

        if conditions:
            query = query.where(and_(*conditions))

        return query

    def _conditions(self, filters: AuditEventFilters) -> list:
        conditions = []

        if filters.date_from is not None:
            conditions.append(cast(AuditLog.timestamp, Date) >= filters.date_from)
        if filters.date_to is not None:
            conditions.append(cast(AuditLog.timestamp, Date) <= filters.date_to)
        if filters.action is not None:
            conditions.append(AuditLog.action == filters.action)
        if filters.entity is not None:
            conditions.append(AuditLog.entity == filters.entity)
        if filters.actor_id is not None:
            conditions.append(AuditLog.user_id == filters.actor_id)
        if filters.entity_id is not None:
            conditions.append(AuditLog.entity_id == filters.entity_id)
        if filters.search:
            conditions.append(AuditLog.description.ilike(f"%{filters.search.strip()}%"))
        if filters.without_actor:
            conditions.append(AuditLog.user_id.is_(None))

        return conditions

    @staticmethod
    def _enum_value(value) -> str:
        return getattr(value, "value", value)
