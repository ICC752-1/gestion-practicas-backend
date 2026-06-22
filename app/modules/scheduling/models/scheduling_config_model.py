"""Modelo ORM para configuración de agendamiento por coordinador."""

from datetime import UTC, datetime
from sqlalchemy import DateTime, ForeignKey, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base


class SchedulingConfig(Base):
    """Representa la configuración de agendamiento individual de un coordinador."""

    __tablename__ = "scheduling_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    coordinator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    general_consultations_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    internship_applications_disabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )

    coordinator = relationship("User")
