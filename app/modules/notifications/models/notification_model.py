"""Modelo ORM de notificaciones.

Este modulo define la entidad `Notification`, utilizada para representar
notificaciones persistentes del sistema asociadas a eventos administrativos
como aprobacion, rechazo, derivacion de practicas y cambios de estado
de requisitos.
"""

import enum
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base


class NotificationEventTypeEnum(str, enum.Enum):
    """Enumeracion de tipos de evento que generan notificaciones."""

    internship_approved = "internship_approved"
    internship_rejected = "internship_rejected"
    internship_derived = "internship_derived"
    requirement_status_changed = "requirement_status_changed"
    appointment_scheduled = "appointment_scheduled"
    custom = "custom"


class NotificationStatusEnum(str, enum.Enum):
    """Enumeracion de estados de una notificacion.

    Attributes:
        simulated: Notificacion registrada sin envio real (modo depuracion).
        pending: Notificacion creada en espera de envio SMTP.
        sent: Notificacion enviada exitosamente via SMTP.
        failed: Notificacion cuyo envio SMTP fallo.
    """

    simulated = "simulated"
    pending = "pending"
    sent = "sent"
    failed = "failed"


class Notification(Base):
    """Representa una notificacion persistente del sistema.

    Attributes:
        id: Identificador entero de la notificacion.
        recipient_user_id: Identificador del usuario destinatario (interno).
        recipient_email: Correo electronico del destinatario (externo).
        event_type: Tipo de evento que genero la notificacion.
        subject: Asunto de la notificacion.
        content: Contenido de la notificacion (texto o HTML).
        status: Estado actual de la notificacion.
        payload: Metadata adicional del evento en formato JSONB.
        created_at: Marca temporal de creacion de la notificacion.
        sent_at: Marca temporal de envio real (null si simulated/failed).
        read_at: Marca temporal de lectura dentro de la plataforma.
        recipient: Relacion ORM hacia el usuario destinatario.
    """

    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipient_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        index=True,
        nullable=True,
    )
    recipient_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    event_type: Mapped[NotificationEventTypeEnum] = mapped_column(
        PGEnum(
            "internship_approved",
            "internship_rejected",
            "internship_derived",
            "requirement_status_changed",
            "appointment_scheduled",
            "custom",
            name="enumNotificationEventType",
            create_type=False,
        ),
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[NotificationStatusEnum] = mapped_column(
        PGEnum(
            "simulated",
            "pending",
            "sent",
            "failed",
            name="enumNotificationStatus",
            create_type=False,
        ),
        nullable=False,
    )
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    recipient = relationship("User", foreign_keys=[recipient_user_id])

    @property
    def is_read(self) -> bool:
        """Indica si el destinatario ya marco la notificacion como leida."""

        return self.read_at is not None
