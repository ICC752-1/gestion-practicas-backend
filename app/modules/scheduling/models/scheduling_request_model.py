"""Modelo ORM para solicitudes de agendamiento."""

from datetime import UTC, date, datetime, time
import enum

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, Time
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base
from app.modules.scheduling.models.presentation_model import (
    PresentationPurposeEnum,
)


class SchedulingRequestStatusEnum(str, enum.Enum):
    """Estados posibles de una solicitud de agendamiento."""

    pending = "pending"
    scheduled = "scheduled"
    rejected = "rejected"
    cancelled = "cancelled"


class SchedulingRequest(Base):
    """Representa una solicitud de agendamiento creada por un estudiante."""

    __tablename__ = "scheduling_request"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    internship_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("internship.id", ondelete="SET NULL"),
        nullable=True,
    )
    purpose: Mapped[PresentationPurposeEnum] = mapped_column(
        PGEnum(
            PresentationPurposeEnum,
            name="enumPresentationPurpose",
            values_callable=lambda values: [item.value for item in values],
            create_type=False,
        ),
        nullable=False,
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_dates: Mapped[str] = mapped_column(Text, nullable=False)  # JSON o listado de fechas sugeridas
    status: Mapped[SchedulingRequestStatusEnum] = mapped_column(
        PGEnum(
            SchedulingRequestStatusEnum,
            name="enumSchedulingRequestStatus",
            values_callable=lambda values: [item.value for item in values],
            create_type=False,
        ),
        default=SchedulingRequestStatusEnum.pending,
        nullable=False,
    )
    coordinator_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    coordinator_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    scheduled_start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    scheduled_end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    scheduled_modality: Mapped[str | None] = mapped_column(
        PGEnum(
            "Presencial",
            "Remoto",
            "Híbrido",
            name="enumModality",
            create_type=False,
        ),
        nullable=True,
    )
    scheduled_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    presentation_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("presentation.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_coordinator_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_by_role: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    document_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("document.id", ondelete="SET NULL"),
        nullable=True,
    )
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
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    student = relationship("User", foreign_keys=[student_id])
    internship = relationship("Internship")
    coordinator = relationship("User", foreign_keys=[coordinator_id])
    target_coordinator = relationship("User", foreign_keys=[target_coordinator_id])
    presentation = relationship("Presentation")
    document = relationship("Document")
