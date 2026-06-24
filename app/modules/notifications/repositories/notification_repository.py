"""Repositorio de acceso a datos para notificaciones.

Este modulo define `NotificationRepository`, encargado de encapsular consultas y
operaciones de persistencia relacionadas con la entidad `Notification` usando una
sesion asincrona de SQLAlchemy.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models.notification_model import (
    Notification,
    NotificationEventTypeEnum,
    NotificationStatusEnum,
)


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class NotificationRepository:
    """Implementa operaciones de lectura y escritura sobre notificaciones.

    Attributes:
        db: Sesion asincrona (`AsyncSession`) utilizada para ejecutar consultas
        y confirmar transacciones.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el repositorio con una sesion de base de datos.

        Args:
            db: Sesion asincrona de SQLAlchemy.
        """

        self.db = db

    async def create(self, notification: Notification) -> Notification:
        """Persiste una notificacion en la base de datos.

        Agrega la entidad a la sesion, confirma la transaccion y refresca la
        instancia para asegurar que campos generados por la base de datos queden
        disponibles en el objeto.

        Args:
            notification: Entidad `Notification` a crear.

        Returns:
            La misma entidad `Notification` persistida y refrescada.
        """

        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)

        return notification

    async def get_by_id(self, notification_id: int) -> Notification | None:
        """Obtiene una notificacion por su identificador.

        Args:
            notification_id: Identificador entero de la notificacion.

        Returns:
            La entidad `Notification` si existe; `None` si no se encuentra.
        """

        query = select(Notification).where(Notification.id == notification_id)
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def get_by_recipient(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
        is_read: bool | None = None,
        event_type: NotificationEventTypeEnum | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> list[Notification]:
        """Lista notificaciones asociadas a un usuario destinatario.

        Args:
            user_id: Identificador entero del usuario destinatario.
            limit: Numero maximo de resultados a retornar.
            offset: Numero de resultados a omitir (paginacion).

        Returns:
            Lista de entidades `Notification` asociadas al usuario.
        """

        query = select(Notification).where(Notification.recipient_user_id == user_id)
        query = self._apply_user_filters(
            query=query,
            is_read=is_read,
            event_type=event_type,
            created_from=created_from,
            created_to=created_to,
        )
        query = query.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def count_by_recipient(
        self,
        user_id: int,
        is_read: bool | None = None,
        event_type: NotificationEventTypeEnum | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> int:
        """Cuenta notificaciones del usuario autenticado con filtros opcionales."""

        query = select(func.count(Notification.id)).where(
            Notification.recipient_user_id == user_id
        )
        query = self._apply_user_filters(
            query=query,
            is_read=is_read,
            event_type=event_type,
            created_from=created_from,
            created_to=created_to,
        )
        result = await self.db.execute(query)

        return int(result.scalar_one())

    async def count_unread_by_recipient(self, user_id: int) -> int:
        """Cuenta notificaciones no leidas del usuario autenticado."""

        query = select(func.count(Notification.id)).where(
            Notification.recipient_user_id == user_id,
            Notification.read_at.is_(None),
        )
        result = await self.db.execute(query)

        return int(result.scalar_one())

    async def mark_as_read_for_recipient(
        self,
        *,
        user_id: int,
        notification_ids: list[int] | None = None,
    ) -> int:
        """Marca notificaciones propias como leidas de forma idempotente."""

        query = select(Notification).where(
            Notification.recipient_user_id == user_id,
            Notification.read_at.is_(None),
        )

        if notification_ids is not None:
            if not notification_ids:
                return 0
            query = query.where(Notification.id.in_(notification_ids))

        result = await self.db.execute(query)
        notifications = list(result.scalars().all())

        if not notifications:
            return 0

        now = _utc_now()
        for notification in notifications:
            notification.read_at = now

        await self.db.commit()

        return len(notifications)

    @staticmethod
    def _apply_user_filters(
        *,
        query,
        is_read: bool | None,
        event_type: NotificationEventTypeEnum | None,
        created_from: datetime | None,
        created_to: datetime | None,
    ):
        if is_read is True:
            query = query.where(Notification.read_at.is_not(None))
        elif is_read is False:
            query = query.where(Notification.read_at.is_(None))

        if event_type is not None:
            query = query.where(Notification.event_type == event_type)

        if created_from is not None:
            query = query.where(Notification.created_at >= created_from)

        if created_to is not None:
            query = query.where(Notification.created_at <= created_to)

        return query

    async def get_by_status(
        self,
        status: NotificationStatusEnum,
        limit: int = 50,
    ) -> list[Notification]:
        """Lista notificaciones filtradas por estado.

        Args:
            status: Estado de la notificacion para filtrar.
            limit: Numero maximo de resultados a retornar.

        Returns:
            Lista de entidades `Notification` con el estado indicado.
        """

        query = (
            select(Notification)
            .where(Notification.status == status)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def update_status(
        self,
        notification_id: int,
        new_status: NotificationStatusEnum,
        sent_at=None,
    ) -> Notification | None:
        """Actualiza el estado de una notificacion.

        Args:
            notification_id: Identificador entero de la notificacion.
            new_status: Nuevo estado a asignar.
            sent_at: Marca temporal de envio (solo si el estado es `sent`).

        Returns:
            La entidad `Notification` actualizada; `None` si no existe.
        """

        notification = await self.get_by_id(notification_id)
        if notification is None:
            return None

        notification.status = new_status
        if sent_at is not None:
            notification.sent_at = sent_at

        await self.db.commit()
        await self.db.refresh(notification)

        return notification
