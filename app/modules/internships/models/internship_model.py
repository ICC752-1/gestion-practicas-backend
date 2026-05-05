"""ORM model for student internships."""

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base


class Internship(Base):
    """Represents an internship request/record associated with a student."""

    __tablename__ = "internship"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(255), nullable=False)
    org_phone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    web: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    schedule: Mapped[str] = mapped_column(String(255), nullable=False)
    days: Mapped[str] = mapped_column(String(255), nullable=False)
    modality: Mapped[str] = mapped_column(
        PGEnum(
            "Presencial",
            "Remoto",
            "Hibrido",
            name="enumModality",
            create_type=False,
        ),
        nullable=False,
    )
    internship_address: Mapped[str] = mapped_column(String(255), nullable=False)
    act_description: Mapped[str] = mapped_column(String(255), nullable=False)
    ben_description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upload_date: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    status_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("currentstate.id"),
        nullable=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    status = relationship("CurrentState", back_populates="internships")
    student = relationship("User")
