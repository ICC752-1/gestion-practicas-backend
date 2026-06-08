"""Controlador HTTP para endpoints de notificaciones.

Este modulo define las rutas relacionadas con la consulta y envio de
notificaciones persistentes. El controlador coordina dependencias de
autenticacion, sesion de base de datos y servicios de dominio.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import config
from app.core.database.database import get_db
from app.modules.auth.dependencies.auth_dependency import get_current_user
from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.auth.models.user_model import User
from app.modules.notifications.repositories.notification_repository import (
    NotificationRepository,
)
from app.modules.notifications.schemas.notification_schema import (
    EmailNotificationRequest,
    NotificationDetailResponse,
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


@router.get("", response_model=list[NotificationListItemResponse])
async def list_notifications(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[NotificationListItemResponse]:
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
    )

    return [
        NotificationListItemResponse.model_validate(notification)
        for notification in notifications
    ]


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
