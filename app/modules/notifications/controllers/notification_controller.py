"""Endpoints para el modulo de notificaciones."""

import logging

from fastapi import APIRouter, HTTPException, status
from app.modules.notifications.services.notification_service import notification_service
from app.modules.notifications.schemas.notification_schema import EmailNotificationRequest, NotificationResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])
logger = logging.getLogger(__name__)

@router.post("/send-email", response_model=NotificationResponse)
async def send_notification(request: EmailNotificationRequest):
    """
    Envía un correo correo electrónico dinámico utilizando SMTP configurado.

    - **to_emails**: Lista de destinatarios (debe ser una lista de correos válidos).
    - **subject**: Asunto del correo.
    - **body**: Contenido del mensaje (acepta etiquetas HTML).
    
    Retorna un objeto NotificationResponse indicando el éxito de la operación.
    """
    logger.debug(f"Recibida solicitud para: {request.to_emails}")
    try:
        await notification_service.send_email(request)
        logger.info(f"Correo enviado exitosamente a {request.to_emails}")
        return NotificationResponse(success=True, message="Correo enviado correctamente")
    except Exception as e:
        logger.error(f"Fallo crítico al enviar correo a {request.to_emails}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Error interno al procesar el envío de correo"
        )