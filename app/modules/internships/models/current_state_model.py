"""ORM model for internship workflow states."""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base


class CurrentState(Base):
    """Represents the current state assigned to an internship."""

    __tablename__ = "currentstate"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    internships = relationship("Internship", back_populates="status")
