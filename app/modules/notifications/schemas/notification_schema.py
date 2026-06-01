"""Schemas Pydantic para el sistema de notificaciones.

Este modulo define las estructuras de datos para las solicitudes y respuesta del
servicio de mensajería, asegurando la validación de tipos y formatos.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import List

class EmailNotificationRequest(BaseModel):
    """
    Payload de solicitud para enviar un correo electrónico.

    Define los campos necesarios para que cualquier módulo del sistema pueda
    disparar una notificación vía SMTP
    """

    to_emails: List[EmailStr] = Field(..., description="Lista de destinatarios")
    subject: str = Field(..., min_length=3, max_length=255)
    body: str = Field(..., min_length=1)

class NotificationResponse(BaseModel):
    """Esquema de respuesta tras un intento de envio de notificación.

    Attributes:
        success: Indica si la operacion fue exitosa.
        message: Detalle informativo sobre el resultado de la operacion.
    """

    success: bool = Field (
        ...,
        description="Indica si el envío fue aceptado por el servidor SMTP"
    )
    message: str = Field(
        ...,
        description="Detalle informativo sobre el resultado o el error ocurrido."
    )