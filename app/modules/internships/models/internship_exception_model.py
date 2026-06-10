"""Modelo ORM para excepciones administrativas de practicas.

Una excepcion administrativa permite que una practica continúe su flujo
pese a no cumplir una regla de negocio base. No reemplaza ni modifica
el valor original del campo exceptuado; solo registra la autorización
con trazabilidad completa.
"""
import enum

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base


class ExceptableRule(str, enum.Enum):
    SCHOOL_INSURANCE = "school_insurance"

class InternshipException(Base):
    """Registra una excepcion administrativa sobre una regla de negocio.

    Una excepcion no modifica el valor del campo original (ej. `has_school_insurance`
    permanece en `False`). Solo habilita el flujo administrativo pese al incumplimiento
    de la regla base, dejando trazabilidad del responsable y la justificacion.

    Attributes:
        id: Identificador primario.
        internship_id: Practica sobre la cual se aplica la excepcion.
        rule: Regla de negocio exceptuada (ej. ``"school_insurance"``).
        reason: Justificacion obligatoria provista por el actor.
        authorized_by: Usuario que autorizo la excepcion.
        authorized_at: Timestamp de la autorizacion.
        internship: Relacion hacia la practica asociada.
        actor: Relacion hacia el usuario autorizador.
    """

    __tablename__ = "internship_exceptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    internship_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("internship.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    rule: Mapped[ExceptableRule] = mapped_column(
        PGEnum(
            ExceptableRule,
            name="exceptable_rule_enum",
            create_type=False,
        ),
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(Text, nullable=False)

    authorized_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    authorized_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )

    internship = relationship("Internship", back_populates="exceptions")
    actor = relationship("User", foreign_keys=[authorized_by])