"""Controlador HTTP para endpoints de notificaciones.

Este modulo define las rutas relacionadas con la consulta y envio de
notificaciones persistentes. El controlador coordina dependencias de
autenticacion, sesion de base de datos y servicios de dominio.
"""

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import config
from app.core.database.database import get_db
from app.modules.auth.dependencies.auth_dependency import get_current_user
from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.auth.models.user_model import User
from app.modules.notifications.models.notification_model import NotificationEventTypeEnum
from app.modules.notifications.repositories.notification_repository import (
    NotificationRepository,
)
from app.modules.notifications.schemas.notification_schema import (
    EmailNotificationRequest,
    MarkNotificationsReadRequest,
    MarkNotificationsReadResponse,
    NotificationDetailResponse,
    NotificationListResponse,
    NotificationListItemResponse,
    NotificationResponse,
    NotificationRetryResponse,
)
from app.modules.notifications.services.notification_service import (
    NotificationService,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])
logger = logging.getLogger(__name__)

SEND_EMAIL_ROLES = [
    "Encargado de practica",
    "Director de carrera",
    "Secretaria de Carrera",
]
RETRY_ROLES = [
    "Encargado de practica",
    "Director de carrera",
]


def _build_service(db: AsyncSession) -> NotificationService:
    """Construye el servicio de notificaciones para un request.

    Args:
        db: Sesion asincrona de SQLAlchemy inyectada por FastAPI.

    Returns:
        Instancia de `NotificationService` configurada con su repositorio.
    """

    return NotificationService(
        notification_repository=NotificationRepository(db),
        app_config=config,
    )


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    is_read: bool | None = Query(default=None),
    event_type: NotificationEventTypeEnum | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
) -> NotificationListResponse:
    """Lista las notificaciones del usuario autenticado.

    Args:
        db: Sesion asincrona de base de datos inyectada por `get_db`.
        current_user: Usuario autenticado obtenido desde el token Bearer.
        limit: Numero maximo de resultados a retornar.
        offset: Desplazamiento para paginacion.

    Returns:
        Lista de notificaciones del usuario ordenadas por fecha descendente.
    """

    service = _build_service(db)
    notifications = await service.get_notifications_for_user(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        is_read=is_read,
        event_type=event_type,
        created_from=created_from,
        created_to=created_to,
    )
    total = await service.count_notifications_for_user(
        user_id=current_user.id,
        is_read=is_read,
        event_type=event_type,
        created_from=created_from,
        created_to=created_to,
    )
    unread_count = await service.count_unread_for_user(user_id=current_user.id)

    return NotificationListResponse(
        items=[
            NotificationListItemResponse.model_validate(notification)
            for notification in notifications
        ],
        total=total,
        unread_count=unread_count,
        limit=limit,
        offset=offset,
    )


@router.get("/unread-count")
async def get_unread_count(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, int]:
    """Obtiene el contador persistente de notificaciones no leidas."""

    service = _build_service(db)
    unread_count = await service.count_unread_for_user(user_id=current_user.id)

    return {"unread_count": unread_count}


@router.patch("/read", response_model=MarkNotificationsReadResponse)
async def mark_selected_notifications_as_read(
    payload: MarkNotificationsReadRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MarkNotificationsReadResponse:
    """Marca varias notificaciones propias como leidas."""

    service = _build_service(db)
    updated_count = await service.mark_notifications_as_read(
        user_id=current_user.id,
        notification_ids=payload.notification_ids,
    )
    unread_count = await service.count_unread_for_user(user_id=current_user.id)

    return MarkNotificationsReadResponse(
        updated_count=updated_count,
        unread_count=unread_count,
    )


@router.patch("/read-all", response_model=MarkNotificationsReadResponse)
async def mark_all_notifications_as_read(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MarkNotificationsReadResponse:
    """Marca todas las notificaciones propias como leidas."""

    service = _build_service(db)
    updated_count = await service.mark_notifications_as_read(user_id=current_user.id)
    unread_count = await service.count_unread_for_user(user_id=current_user.id)

    return MarkNotificationsReadResponse(
        updated_count=updated_count,
        unread_count=unread_count,
    )


@router.patch("/{notification_id}/read", response_model=MarkNotificationsReadResponse)
async def mark_notification_as_read(
    notification_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MarkNotificationsReadResponse:
    """Marca una notificacion propia como leida de forma idempotente."""

    service = _build_service(db)
    updated_count = await service.mark_notifications_as_read(
        user_id=current_user.id,
        notification_ids=[notification_id],
    )
    unread_count = await service.count_unread_for_user(user_id=current_user.id)

    return MarkNotificationsReadResponse(
        updated_count=updated_count,
        unread_count=unread_count,
    )


@router.get("/{notification_id}", response_model=NotificationDetailResponse)
async def get_notification(
    notification_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NotificationDetailResponse:
    """Obtiene el detalle de una notificacion por identificador.

    La consulta exige que la notificacion exista y que el usuario sea
    el destinatario de la misma.

    Args:
        notification_id: Identificador entero de la notificacion solicitada.
        db: Sesion asincrona de base de datos inyectada por `get_db`.
        current_user: Usuario autenticado obtenido desde el token Bearer.

    Returns:
        `NotificationDetailResponse` con el detalle de la notificacion.

    Raises:
        HTTPException: Con codigo 404 si la notificacion no existe.
        HTTPException: Con codigo 403 si el usuario no es el destinatario.
    """

    service = _build_service(db)
    notification = await service.get_by_id(notification_id)

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    if notification.recipient_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    return NotificationDetailResponse.model_validate(notification)


@router.post("/send-email", response_model=NotificationResponse)
async def send_notification(
    request: EmailNotificationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(SEND_EMAIL_ROLES))],
) -> NotificationResponse:
    """Envia un correo electronico dinamico utilizando SMTP configurado.

    Requiere que el usuario autenticado posea uno de los roles autorizados.
    Este endpoint mantiene compatibilidad con el flujo original de envio
    directo sin persistencia.

    Args:
        request: Payload con destinatarios, asunto y cuerpo del correo.
        db: Sesion asincrona de base de datos inyectada por `get_db`.
        current_user: Usuario autenticado validado por `require_roles`.

    Returns:
        `NotificationResponse` indicando el exito de la operacion.

    Raises:
        HTTPException: Con codigo 500 si falla el envio SMTP.
        HTTPException: Con codigo 400 si el servicio esta en modo simulated.
    """

    logger.debug(f"Recibida solicitud para: {request.to_emails}")
    service = _build_service(db)

    try:
        await service.send_email(request)
        logger.info(f"Correo enviado exitosamente a {request.to_emails}")
        return NotificationResponse(
            success=True,
            message="Correo enviado correctamente",
        )
    except RuntimeError as exc:
        logger.warning(str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(
            f"Fallo critico al enviar correo a {request.to_emails}: {str(exc)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al procesar el envio de correo",
        ) from exc


@router.post("/{notification_id}/retry", response_model=NotificationRetryResponse)
async def retry_notification(
    notification_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RETRY_ROLES))],
) -> NotificationRetryResponse:
    """Reintenta el envio de una notificacion fallida o pendiente.

    Args:
        notification_id: Identificador de la notificacion a reenviar.
        db: Sesion asincrona de base de datos inyectada por `get_db`.
        current_user: Usuario autenticado validado por `require_roles`.

    Returns:
        `NotificationRetryResponse` con el resultado del reintento.

    Raises:
        HTTPException: Con codigo 404 si la notificacion no existe o no
            es elegible para reintento.
    """

    service = _build_service(db)
    notification = await service.retry_send(notification_id)

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or not eligible for retry",
        )

    success = notification.status == "sent"
    message = (
        "Notificacion enviada exitosamente"
        if success
        else "Fallo el reintento de envio"
    )

    return NotificationRetryResponse(
        success=success,
        message=message,
        notification_id=notification.id,
        status=notification.status,
    )
