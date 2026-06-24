"""Modelo ORM de requisitos de prácticas de estudiantes."""

from datetime import UTC, datetime
import enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class StudentInternshipRequirement(Base):
    """Representa un requisito académico de práctica asociado a un estudiante.

    Esta entidad no representa una práctica registrada. Para eso existe
    `Internship`.
    """

    __tablename__ = "studentinternshiprequirement"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "type",
            name="uq_student_internship_requirement_user_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(
        PGEnum(
            "Práctica de Estudio I",
            "Práctica de Estudio II",
            "Tesis",
            "Práctica Controlada",
            name="enumStudentInternshipType",
            create_type=False,
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        PGEnum(
            "Pendiente",
            "Habilitada",
            "En revisión",
            "Aprobada",
            "Rechazada",
            name="enumStudentInternshipStatus",
            create_type=False,
        ),
        default="Pendiente",
        nullable=False,
    )
    status_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    status_updated_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utc_now_naive,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utc_now_naive,
        onupdate=_utc_now_naive,
        nullable=False,
    )

    student = relationship("User", foreign_keys=[user_id])

class RegistrationRequirementType(str, enum.Enum):
    SCHOOL_INSURANCE = "school_insurance"
    INDUCTION = "induction"

class StudentRegistrationRequirement(Base):
    __tablename__ = "student_registration_requirements"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "requirement",
            name="uq_student_registration_requirement",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    requirement: Mapped[RegistrationRequirementType] = mapped_column(
        PGEnum(
            RegistrationRequirementType,
            name="registration_requirement_enum",
            values_callable=lambda x: [e.value for e in x],
            create_type=False,
        ),
        nullable=False,
    )

    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    updated_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )
