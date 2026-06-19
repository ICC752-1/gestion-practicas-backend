"""Historial del estado local del expediente documental DIRAE."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base
from app.modules.internships.models.internship_model import DiraeStatusEnum


class InternshipDiraeStatusHistory(Base):
    """Registra cambios del expediente DIRAE sin alterar el estado administrativo."""

    __tablename__ = "internship_dirae_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internship_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("internship.id"),
        nullable=False,
    )
    previous_status: Mapped[DiraeStatusEnum | None] = mapped_column(
        PGEnum(
            DiraeStatusEnum,
            name="enumDiraeStatus",
            values_callable=lambda x: [e.value for e in x],
            create_type=False,
        ),
        nullable=True,
    )
    new_status: Mapped[DiraeStatusEnum] = mapped_column(
        PGEnum(
            DiraeStatusEnum,
            name="enumDiraeStatus",
            values_callable=lambda x: [e.value for e in x],
            create_type=False,
        ),
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

    internship = relationship("Internship", back_populates="dirae_status_history")
    actor = relationship("User", foreign_keys=[actor_id])
