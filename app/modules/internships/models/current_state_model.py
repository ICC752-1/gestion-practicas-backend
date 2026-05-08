"""Modelo ORM de estados de practicas.

Este modulo define la entidad `CurrentState`, usada para representar estados
funcionales que puede tener una practica durante su ciclo de revision.
"""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base


class CurrentState(Base):
    """Representa un estado asignable a una practica.

    Attributes:
        id: Identificador entero del estado.
        title: Nombre corto del estado.
        description: Descripcion funcional del estado.
        internships: Relacion ORM con las practicas que usan este estado.
    """

    __tablename__ = "currentstate"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    internships = relationship("Internship", back_populates="status")
