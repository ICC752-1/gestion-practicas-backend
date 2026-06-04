"""Modelo ORM de historial de estados de practicas.

Este modulo define la entidad `InternshipStatusHistory`, usada para registrar
transiciones de estado de una practica sin mezclar esta trazabilidad funcional
con la auditoria tecnica general del sistema.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base


class InternshipStatusHistory(Base):
    """Representa una transicion de estado de una practica.

    Attributes:
        id: Identificador entero del historial.
        internship_id: Identificador de la practica asociada.
        previous_status_id: Estado anterior, si existia.
        new_status_id: Estado nuevo asignado a la practica.
        actor_id: Usuario que ejecuta o dispara la transicion.
        reason: Motivo funcional de la transicion, si corresponde.
        changed_at: Fecha y hora de registro de la transicion.
        metadata_json: Datos auxiliares de contexto almacenados como JSON.
        internship: Relacion ORM hacia la practica.
        previous_status: Relacion ORM hacia el estado anterior.
        new_status: Relacion ORM hacia el estado nuevo.
        actor: Relacion ORM hacia el usuario actor.
    """

    __tablename__ = "internship_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internship_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("internship.id"),
        nullable=False,
    )
    previous_status_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("currentstate.id"),
        nullable=True,
    )
    new_status_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("currentstate.id"),
        nullable=False,
    )
    actor_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )
    metadata_json: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )

    internship = relationship("Internship", back_populates="status_history")
    previous_status = relationship(
        "CurrentState",
        foreign_keys=[previous_status_id],
    )
    new_status = relationship(
        "CurrentState",
        foreign_keys=[new_status_id],
    )
    actor = relationship("User")
