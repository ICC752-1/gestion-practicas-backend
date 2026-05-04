"""Modelo ORM de asignación de roles a usuarios.

Este módulo define la entidad `UserRole`, que representa la relación (muchos a
muchos) entre usuarios y roles.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.core.database.database import Base


class UserRole(Base):
    """Representa la asignación de un rol a un usuario.

    Esta tabla de asociación vincula `User` con `Role` y puede almacenar
    metadatos de la asignación, como la fecha en la que fue otorgado el rol.

    Además, aplica una restricción de unicidad sobre `(user_id, role_id)` para
    evitar asignaciones duplicadas.

    Attributes:
        id: Identificador entero de la asignación (clave primaria).
        user_id: Identificador entero del usuario asociado.
        role_id: Identificador entero del rol asociado.
        assigned_at: Marca temporal (UTC) de asignación/última actualización.
        user: Relación ORM hacia la entidad `User`.
        role: Relación ORM hacia la entidad `Role`.
    """

    __tablename__ = "user_roles"

    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )

    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="roles")
    role = relationship("Role", back_populates="users")
