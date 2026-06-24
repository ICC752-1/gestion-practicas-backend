"""Schemas Pydantic para el sistema de notificaciones.

Este modulo define las estructuras de datos para las solicitudes y respuestas
del servicio de notificaciones, asegurando la validacion de tipos y formatos.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.notifications.models.notification_model import (
    NotificationEventTypeEnum,
    NotificationStatusEnum,
)


class EmailNotificationRequest(BaseModel):
    """Payload de solicitud para enviar un correo electronico.

    Define los campos necesarios para que cualquier modulo del sistema pueda
    disparar una notificacion via SMTP. Este endpoint mantiene compatibilidad
    con el flujo original de envio directo.
    """

    to_emails: list[EmailStr] = Field(..., description="Lista de destinatarios")
    subject: str = Field(..., min_length=3, max_length=255)
    body: str = Field(..., min_length=1)


class NotificationResponse(BaseModel):
    """Esquema de respuesta tras un intento de envio de notificacion.

    Attributes:
        success: Indica si la operacion fue exitosa.
        message: Detalle informativo sobre el resultado de la operacion.
    """

    success: bool = Field(
        ...,
        description="Indica si el envio fue aceptado por el servidor SMTP"
    )
    message: str = Field(
        ...,
        description="Detalle informativo sobre el resultado o el error ocurrido."
    )


class NotificationListItemResponse(BaseModel):
    """Esquema de respuesta para una notificacion en listado.

    Attributes:
        id: Identificador de la notificacion.
        event_type: Tipo de evento que genero la notificacion.
        subject: Asunto de la notificacion.
        status: Estado actual de la notificacion.
        created_at: Marca temporal de creacion.
        sent_at: Marca temporal de envio real (puede ser null).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: NotificationEventTypeEnum
    subject: str
    status: NotificationStatusEnum
    created_at: datetime
    sent_at: datetime | None = None
    read_at: datetime | None = None
    is_read: bool


class NotificationListResponse(BaseModel):
    """Respuesta paginada para notificaciones del usuario autenticado."""

    items: list[NotificationListItemResponse]
    total: int
    unread_count: int
    limit: int
    offset: int


class NotificationDetailResponse(BaseModel):
    """Esquema de respuesta para el detalle de una notificacion.

    Attributes:
        id: Identificador de la notificacion.
        recipient_user_id: Identificador del usuario destinatario.
        recipient_email: Correo electronico del destinatario.
        event_type: Tipo de evento que genero la notificacion.
        subject: Asunto de la notificacion.
        content: Contenido de la notificacion.
        status: Estado actual de la notificacion.
        payload: Metadata adicional del evento.
        created_at: Marca temporal de creacion.
        sent_at: Marca temporal de envio real.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    recipient_user_id: int | None = None
    recipient_email: str | None = None
    event_type: NotificationEventTypeEnum
    subject: str
    content: str
    status: NotificationStatusEnum
    payload: dict[str, Any] | None = Field(
        default=None,
        validation_alias="payload",
    )
    created_at: datetime
    sent_at: datetime | None = None
    read_at: datetime | None = None
    is_read: bool


class MarkNotificationsReadRequest(BaseModel):
    """Payload para marcar varias notificaciones propias como leidas."""

    notification_ids: list[int] = Field(default_factory=list)


class MarkNotificationsReadResponse(BaseModel):
    """Respuesta de operaciones idempotentes de lectura."""

    updated_count: int
    unread_count: int


class NotificationRetryResponse(BaseModel):
    """Esquema de respuesta tras reintentar el envio de una notificacion.

    Attributes:
        success: Indica si el reintento fue exitoso.
        message: Detalle informativo sobre el resultado.
        notification_id: Identificador de la notificacion reintentada.
        status: Estado actualizado de la notificacion tras el reintento.
    """

    success: bool
    message: str
    notification_id: int
    status: NotificationStatusEnum
