"""Modelo ORM de usuarios.

Este módulo define la entidad `User` utilizada por el sistema de autenticación y
autorización.
"""

from datetime import datetime, timezone
from uuid import uuid4, UUID

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.core.database import Base

class User(Base):
    """Representa un usuario del sistema.

    La entidad `User` almacena las credenciales y el estado del usuario, así como
    su relación con roles (normalmente mediante una tabla de asociación como
    `UserRole`).

    Attributes:
        id: Identificador UUID del usuario (clave primaria).
        email: Correo electrónico único del usuario.
        password_hash: Hash de la contraseña del usuario.
        is_active: Indica si la cuenta está activa.
        is_verified: Indica si la cuenta ha sido verificada.
        created_at: Marca temporal (UTC) de creación/última actualización.
        roles: Relación con asignaciones de roles del usuario.
    """

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
