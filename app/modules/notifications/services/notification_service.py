"""Servicio de notificaciones con soporte dual-mode (simulated/real).

Este modulo define `NotificationService`, encargado de gestionar la creacion
y despacho de notificaciones persistentes. Soporta dos modos de operacion:

- **simulated**: Las notificaciones se persisten con estado `simulated` sin
  realizar envio SMTP. Ideal para desarrollo y depuracion.
- **real**: Las notificaciones se persisten y se envian via SMTP utilizando
  la configuracion de correo electronico definida en las variables de entorno.
"""

import logging
from datetime import UTC, datetime
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from app.core.config import config
from app.modules.notifications.models.notification_model import (
    Notification,
    NotificationEventTypeEnum,
    NotificationStatusEnum,
)
from app.modules.notifications.repositories.notification_repository import (
    NotificationRepository,
)
from app.modules.notifications.schemas.notification_schema import (
    EmailNotificationRequest,
)

logger = logging.getLogger(__name__)


class NotificationService:
    """Orquesta la creacion y despacho de notificaciones persistentes.

    Attributes:
        repository: Repositorio de acceso a datos para notificaciones.
        mode: Modo de operacion (`simulated` o `real`).
        _mailer: Instancia de `FastMail` configurada solo si mode es `real`.
    """

    def __init__(
        self,
        notification_repository: NotificationRepository,
        app_config: type | object = config,
    ) -> None:
        """Inicializa el servicio con sus dependencias y configura el modo.

        Si el modo es `real` pero las credenciales SMTP son las valores por
        defecto (no configurados), el servicio cae automaticamente a modo
        `simulated` y emite una advertencia en el log.

        Args:
            notification_repository: Repositorio para operaciones de persistencia.
            app_config: Objeto de configuracion de la aplicacion (por defecto
                el singleton global `config`).
        """

        self.repository = notification_repository
        self.mode = getattr(app_config, "NOTIFICATION_MODE", "simulated")
        self._app_config = app_config
        self._mailer: FastMail | None = None

        if self.mode == "real":
            self._mailer = self._build_mailer(app_config)

    @staticmethod
    def _build_mailer(app_config: type | object) -> FastMail | None:
        """Construye la instancia de FastMail a partir de la configuracion SMTP.

        Si las credenciales SMTP corresponden a los valores por defecto,
        retorna `None` y emite una advertencia.

        Args:
            app_config: Objeto de configuracion con atributos MAIL_*.

        Returns:
            Instancia de `FastMail` si la configuracion es valida;
            `None` si las credenciales son las por defecto.
        """

        if (
            getattr(app_config, "MAIL_USERNAME", "") == "test@example.com"
            or getattr(app_config, "MAIL_PASSWORD", "") == "password"
        ):
            logger.warning(
                "Credenciales SMTP no configuradas. "
                "El servicio de notificaciones operara en modo simulated."
            )
            return None

        connection_config = ConnectionConfig(
            MAIL_USERNAME=getattr(app_config, "MAIL_USERNAME", ""),
            MAIL_PASSWORD=getattr(app_config, "MAIL_PASSWORD", ""),
            MAIL_FROM=getattr(app_config, "MAIL_FROM", ""),
            MAIL_PORT=getattr(app_config, "MAIL_PORT", 587),
            MAIL_SERVER=getattr(app_config, "MAIL_SERVER", "localhost"),
            MAIL_STARTTLS=getattr(app_config, "MAIL_STARTTLS", False),
            MAIL_SSL_TLS=getattr(app_config, "MAIL_SSL_TLS", False),
            USE_CREDENTIALS=True,
        )

        return FastMail(connection_config)

    async def create_and_dispatch(
        self,
        notification: Notification,
    ) -> Notification:
        """Persiste una notificacion y la despacha segun el modo configurado.

        En modo `simulated`, la notificacion se persiste directamente con
        estado `simulated` sin envio SMTP. En modo `real`, se persiste con
        estado `pending` y se intenta el envio inmediato.

        Args:
            notification: Entidad `Notification` construida previamente
                (tipicamente via un helper de eventos).

        Returns:
            La entidad `Notification` persistida con su estado actualizado.
        """

        if self.mode != "real" or self._mailer is None:
            notification.status = NotificationStatusEnum.simulated
            persisted = await self.repository.create(notification)
            logger.info(
                "Notificacion simulada creada (id=%s, event=%s, recipient=%s)",
                persisted.id,
                persisted.event_type,
                persisted.recipient_user_id or persisted.recipient_email,
            )
            return persisted

        notification.status = NotificationStatusEnum.pending
        persisted = await self.repository.create(notification)

        try:
            await self._send_smtp(persisted)
            now = datetime.now(UTC).replace(tzinfo=None)
            persisted = await self.repository.update_status(
                notification_id=persisted.id,
                new_status=NotificationStatusEnum.sent,
                sent_at=now,
            )
            logger.info(
                "Notificacion enviada via SMTP (id=%s, event=%s)",
                persisted.id,
                persisted.event_type,
            )
        except Exception as exc:
            logger.error(
                "Fallo envio SMTP para notificacion id=%s: %s",
                persisted.id,
                str(exc),
                exc_info=True,
            )
            persisted = await self.repository.update_status(
                notification_id=persisted.id,
                new_status=NotificationStatusEnum.failed,
            )

        return persisted

    async def send_email(self, request: EmailNotificationRequest) -> bool:
        """Envia un correo electronico via SMTP (compatibilidad con endpoint existente).

        Este metodo mantiene compatibilidad con el flujo original de envio de
        correo directo sin persistencia. Se utiliza unicamente desde el endpoint
        `POST /notifications/send-email`.

        Args:
            request: Datos del correo a enviar.

        Returns:
            `True` si el envio fue exitoso.

        Raises:
            RuntimeError: Si el servicio esta en modo simulated y no hay
                mailer SMTP configurado.
            Exception: Propaga cualquier error de conexion o autenticacion SMTP.
        """

        if self._mailer is None:
            raise RuntimeError(
                "El servicio de notificaciones esta en modo simulated. "
                "No se puede enviar correo real sin configuracion SMTP."
            )

        message = MessageSchema(
            subject=request.subject,
            recipients=request.to_emails,
            body=request.body,
            subtype=MessageType.html,
        )

        await self._mailer.send_message(message)

        logger.info(
            "Envio SMTP directo exitoso a %d destinatario(s)",
            len(request.to_emails),
        )

        return True

    async def retry_send(self, notification_id: int) -> Notification | None:
        """Reintenta el envio de una notificacion fallida o pendiente.

        Args:
            notification_id: Identificador de la notificacion a reenviar.

        Returns:
            La entidad `Notification` actualizada; `None` si no existe
            o si el mailer no esta configurado.
        """

        if self._mailer is None:
            logger.warning(
                "Reintento de envio ignorado: mailer no configurado (id=%s)",
                notification_id,
            )
            return None

        notification = await self.repository.get_by_id(notification_id)
        if notification is None:
            return None

        if notification.status not in (
            NotificationStatusEnum.failed,
            NotificationStatusEnum.pending,
        ):
            return None

        try:
            await self._send_smtp(notification)
            now = datetime.now(UTC).replace(tzinfo=None)
            return await self.repository.update_status(
                notification_id=notification.id,
                new_status=NotificationStatusEnum.sent,
                sent_at=now,
            )
        except Exception as exc:
            logger.error(
                "Reintento fallido para notificacion id=%s: %s",
                notification.id,
                str(exc),
                exc_info=True,
            )
            return await self.repository.update_status(
                notification_id=notification.id,
                new_status=NotificationStatusEnum.failed,
            )

    async def get_notifications_for_user(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
        is_read: bool | None = None,
        event_type: NotificationEventTypeEnum | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> list[Notification]:
        """Obtiene las notificaciones asociadas a un usuario.

        Args:
            user_id: Identificador del usuario destinatario.
            limit: Numero maximo de resultados.
            offset: Desplazamiento para paginacion.

        Returns:
            Lista de notificaciones del usuario ordenadas por fecha descendente.
        """

        return await self.repository.get_by_recipient(
            user_id=user_id,
            limit=limit,
            offset=offset,
            is_read=is_read,
            event_type=event_type,
            created_from=created_from,
            created_to=created_to,
        )

    async def count_notifications_for_user(
        self,
        user_id: int,
        is_read: bool | None = None,
        event_type: NotificationEventTypeEnum | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> int:
        """Cuenta notificaciones del usuario autenticado con filtros."""

        return await self.repository.count_by_recipient(
            user_id=user_id,
            is_read=is_read,
            event_type=event_type,
            created_from=created_from,
            created_to=created_to,
        )

    async def count_unread_for_user(self, user_id: int) -> int:
        """Cuenta notificaciones no leidas del usuario autenticado."""

        return await self.repository.count_unread_by_recipient(user_id=user_id)

    async def mark_notifications_as_read(
        self,
        user_id: int,
        notification_ids: list[int] | None = None,
    ) -> int:
        """Marca notificaciones propias como leidas de forma idempotente."""

        return await self.repository.mark_as_read_for_recipient(
            user_id=user_id,
            notification_ids=notification_ids,
        )

    async def get_by_id(self, notification_id: int) -> Notification | None:
        """Obtiene una notificacion por su identificador.

        Args:
            notification_id: Identificador entero de la notificacion.

        Returns:
            La entidad `Notification` si existe; `None` si no se encuentra.
        """

        return await self.repository.get_by_id(notification_id)

    async def _send_smtp(self, notification: Notification) -> None:
        """Envia una notificacion persistente via SMTP.

        Args:
            notification: Entidad `Notification` a enviar.

        Raises:
            Exception: Propaga cualquier error del transporte SMTP.
        """

        if self._mailer is None:
            raise RuntimeError("Mailer SMTP no configurado")

        recipients: list[str] = []
        if notification.recipient_email:
            recipients.append(notification.recipient_email)

        if not recipients:
            raise ValueError(
                f"La notificacion id={notification.id} no tiene destinatario de correo"
            )

        message = MessageSchema(
            subject=notification.subject,
            recipients=recipients,
            body=notification.content,
            subtype=MessageType.html,
        )

        await self._mailer.send_message(message)
