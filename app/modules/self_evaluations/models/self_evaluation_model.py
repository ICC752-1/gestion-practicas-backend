"""Modelos ORM para autoevaluaciones de estudiantes."""

from datetime import UTC, datetime
import enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SelfEvaluationStatusEnum(str, enum.Enum):
    """Estados funcionales de una autoevaluacion."""

    draft = "draft"
    submitted = "submitted"
    reopened = "reopened"


class SelfEvaluation(Base):
    """Autoevaluacion unica de un estudiante para una practica."""

    __tablename__ = "self_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "internship_id",
            "student_id",
            name="uq_self_evaluation_internship_student",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internship_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("internship.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    form_version: Mapped[str] = mapped_column(String(50), nullable=False)
    criteria_snapshot: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    responses: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    observations: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[SelfEvaluationStatusEnum] = mapped_column(
        PGEnum(
            SelfEvaluationStatusEnum,
            name="enumSelfEvaluationStatus",
            values_callable=lambda x: [e.value for e in x],
            create_type=False,
        ),
        default=SelfEvaluationStatusEnum.draft,
        nullable=False,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reopened_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reopen_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utc_now,
        onupdate=_utc_now,
        nullable=False,
    )

    internship = relationship("Internship")
    student = relationship("User", foreign_keys=[student_id])
    reopen_actor = relationship("User", foreign_keys=[reopened_by])
