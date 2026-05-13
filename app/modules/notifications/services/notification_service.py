"""Servicio global de notificaciones.

Provee la logica para conectar con el servidor SMTP y enviar correos
electronicos a destinatarios dinámicos proporcionados por otros modulos.
"""

import os
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from app.modules.notifications.schemas.notification_schema import EmailNotificationRequest
from app.core.config import config

class NotificationService:
    """Clase para gestionar envios de correo de forma centralizada."""

    def __init__(self):
        """Configura el remitente (quien envia) usando el archivo .env."""
        self.config = ConnectionConfig(
            MAIL_USERNAME=config.mail_username,
            MAIL_PASSWORD=config.mail_password,
            MAIL_FROM=config.mail_from,
            MAIL_PORT=config.mail_port,
            MAIL_SERVER=config.mail_server,
            MAIL_STARTTLS=config.mail_starttls,
            MAIL_SSL_TLS=config.mail_ssl_tls,
            USE_CREDENTIALS=True
        )

    async def send_email(self, request: EmailNotificationRequest) -> bool:
        """Procesa el envío a los destinatarios dinámicos.

        Args:
            request: Contiene los datos dinámicos (to_emails, subject, body).
        """
        message = MessageSchema(
            subject=request.subject,
            recipients=request.to_emails, # Destinatarios obtenidos dinámicamente
            body=request.body,
            subtype=MessageType.html
        )

        fm = FastMail(self.config)
        await fm.send_message(message)
        return True

# Única instancia para todo el sistema
notification_service = NotificationService()