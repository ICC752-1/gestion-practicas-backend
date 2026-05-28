"""Servicio global de notificaciones.

Provee la lógica para conectar con el servidor SMTP y enviar correos
electrónicos a destinatarios dinámicos proporcionados por otros módulos.
"""

import logging
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from app.modules.notifications.schemas.notification_schema import (
    EmailNotificationRequest,
)
from app.core.config import config

# Configuración del logger para este servicio
logger = logging.getLogger(__name__)


class NotificationService:
    """Clase para gestionar envíos de correo de forma centralizada."""

    def __init__(self):
        """
        Configura los parámetros de conexión SMTP.

        Utiliza los valores cargados en el objeto 'config' desde el archivo .env.
        La configuración está optimizada para Gmail usando el puerto 587 (TLS).
        """

        self.config = ConnectionConfig(
            MAIL_USERNAME=config.MAIL_USERNAME,
            MAIL_PASSWORD=config.MAIL_PASSWORD,
            MAIL_FROM=config.MAIL_FROM,
            MAIL_PORT=config.MAIL_PORT,
            MAIL_SERVER=config.MAIL_SERVER,
            MAIL_STARTTLS=config.MAIL_STARTTLS,
            MAIL_SSL_TLS=config.MAIL_SSL_TLS,
            USE_CREDENTIALS=True,
        )

    async def send_email(self, request: EmailNotificationRequest) -> bool:
        """
        Procesa el envío del mensaje a los destinatarios especificados.

        Args:
            request (EmailNotificationRequest): Datos dinámicos del correo.

         Returns:
            bool: True si el mensaje se entregó al servidor SMTP.

         Raises:
            Exception: Propaga cualquier error de conexión o autenticación
                       para que sea manejado por el controlador.
        """
        logger.debug(f"Construyendo mensaje para: {request.to_emails}")

        message = MessageSchema(
            subject=request.subject,
            recipients=request.to_emails,
            body=request.body,
            subtype=MessageType.html,
        )

        try:
            fm = FastMail(self.config)
            await fm.send_message(message)

            # log de éxito a nivel interno
            logger.info(
                f"Envio SMTP exitoso a {len(request.to_emails)} destinatario(s)"
            )
            return True

        except Exception as e:
            # Registramos el error antes de propagarlo al controlador
            logger.error(
                f"Error en el transporte SMTP hacia {request.to_emails}: {str(e)}",
                exc_info=True,
            )
            raise e


# Única instancia para todo el sistema
notification_service = NotificationService()
