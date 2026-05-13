"""Schemas Pydantic para el sistema de notificaciones.

Este modulo define los modelos de datos para el envio de comunicaciones,
especificamente para el servicio global de mensajeria por correo electronico
que sera consumido por otros modulos del sistema.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional

class EmailNotificationRequest(BaseModel):
    """Payload de solicitud para enviar un correo electronico.

    Attributes:
        to_emails: Lista de correos electronicos de los destinatarios.
        subject: Asunto del mensaje.
            Restricciones: longitud minima 3 y maxima 255 caracteres.
        body: Contenido del mensaje (soporta formato HTML).
            Restricciones: longitud minima 1 caracter.
    """

    to_emails: List[EmailStr] = Field(..., description="Lista de destinatarios")
    subject: str = Field(..., min_length=3, max_length=255)
    body: str = Field(..., min_length=1)

class NotificationResponse(BaseModel):
    """Esquema de respuesta tras un intento de envio de notificacion.

    Attributes:
        success: Indica si la operacion fue exitosa.
        message: Detalle informativo sobre el resultado de la operacion.
    """

    success: bool
    message: str