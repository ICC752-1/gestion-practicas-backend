"""Endpoints para el modulo de notificaciones."""

from fastapi import APIRouter, HTTPException
from app.modules.notifications.services.notification_service import notification_service
from app.modules.notifications.schemas.notification_schema import EmailNotificationRequest, NotificationResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.post("/send-email", response_model=NotificationResponse)
async def send_notification(request: EmailNotificationRequest):
    """Endpoint para probar el envio de correos dinamicos."""
    try:
        await notification_service.send_email(request)
        return NotificationResponse(success=True, message="Correo enviado correctamente")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))