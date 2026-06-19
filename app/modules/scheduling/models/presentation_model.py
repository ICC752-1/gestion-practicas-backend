"""Modelo ORM para agenda de entrevistas y presentaciones."""

from datetime import UTC, date, datetime, time
import enum

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, Time
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base


class PresentationPurposeEnum(str, enum.Enum):
    """Tipos de instancias agendables para una practica."""

    initial_interview = "initial_interview"
    final_presentation = "final_presentation"


class PresentationStatusEnum(str, enum.Enum):
    """Estados de un bloque de agenda."""

    available = "available"
    scheduled = "scheduled"
    completed = "completed"
    cancelled = "cancelled"
    no_show = "no_show"
    closed = "closed"


class Presentation(Base):
    """Representa un bloque publicado o reservado en la agenda."""

    __tablename__ = "presentation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
    )
    modality: Mapped[str] = mapped_column(
        PGEnum(
            "Presencial",
            "Remoto",
            "Híbrido",
            name="enumModality",
            create_type=False,
        ),
        nullable=False,
    )
    purpose: Mapped[PresentationPurposeEnum] = mapped_column(
        PGEnum(
            PresentationPurposeEnum,
            name="enumPresentationPurpose",
            values_callable=lambda values: [item.value for item in values],
            create_type=False,
        ),
        default=PresentationPurposeEnum.initial_interview,
        nullable=False,
    )
    status: Mapped[PresentationStatusEnum] = mapped_column(
        PGEnum(
            PresentationStatusEnum,
            name="enumPresentationStatus",
            values_callable=lambda values: [item.value for item in values],
            create_type=False,
        ),
        default=PresentationStatusEnum.available,
        nullable=False,
    )
    result: Mapped[str | None] = mapped_column(
        PGEnum(
            "Pendiente",
            "Aprobada",
            "Reprobado",
            name="enumResult",
            create_type=False,
        ),
        nullable=True,
    )
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(
        String(64),
        default="America/Santiago",
        nullable=False,
    )
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )
    reserved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    internship_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("internship.id"),
        nullable=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )
    owner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    internship = relationship("Internship")
    student = relationship("User", foreign_keys=[user_id])
    owner = relationship("User", foreign_keys=[owner_id])
