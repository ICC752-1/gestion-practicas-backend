"""Modelo ORM de roles.

Este módulo define la entidad `Role` utilizada por el sistema de autenticación y
autorización.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.core.database.database import Base


class Role(Base):
    """Representa un rol de autorización del sistema.

    Un `Role` define un conjunto de permisos/capacidades que puede asignarse a
    usuarios (normalmente mediante una tabla de asociación, p. ej. `UserRole`).

    Attributes:
        id: Identificador entero del rol (clave primaria).
        name: Nombre único del rol.
        description: Descripción legible del rol.
        created_at: Marca temporal (UTC) de creación/última actualización.
        users: Relación con asignaciones de usuarios a roles.
    """

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        PGEnum(
            "Estudiante",
            "Supervisor de practica",
            "Encargado de practica",
            "Director de carrera",
            "Secretaria de Carrera",
            name="enumRole",
            create_type=False,
        ),
        unique=True,
        index=True,
        nullable=False,
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    users = relationship(
        "UserRole", back_populates="role", cascade="all, delete-orphan"
    )
