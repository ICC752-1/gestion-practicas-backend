"""Modelo ORM de roles.

Este módulo define la entidad `Role` utilizada por el sistema de autenticación y
autorización.
"""

from datetime import datetime, timezone
from uuid import uuid4, UUID

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

# from app.core.database import Base

class Role(Base):
    """Representa un rol de autorización del sistema.

    Un `Role` define un conjunto de permisos/capacidades que puede asignarse a
    usuarios (normalmente mediante una tabla de asociación, p. ej. `UserRole`).

    Attributes:
        id: Identificador UUID del rol (clave primaria).
        name: Nombre único del rol.
        description: Descripción legible del rol.
        created_at: Marca temporal (UTC) de creación/última actualización.
        users: Relación con asignaciones de usuarios a roles.
    """

    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    users = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")