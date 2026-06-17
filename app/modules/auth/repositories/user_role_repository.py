"""Repositorio de acceso a datos para asignaciones de roles.

Este modulo define `UserRoleRepository`, encargado de encapsular consultas y
operaciones de persistencia relacionadas con la entidad `UserRole` usando una
sesion asincrona de SQLAlchemy.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models.user_role_model import UserRole


class UserRoleRepository:
    """Implementa operaciones de lectura y escritura sobre asignaciones de roles.

    Attributes:
        db: Sesion asincrona (`AsyncSession`) utilizada para ejecutar consultas
            y confirmar transacciones.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el repositorio con una sesion de base de datos.

        Args:
            db: Sesion asincrona de SQLAlchemy.
        """

        self.db = db

    async def list_roles_for_user(self, user_id: int) -> list[UserRole]:
        """Lista las asignaciones de roles de un usuario.

        Args:
            user_id: Identificador entero del usuario.

        Returns:
            Lista de entidades `UserRole` asociadas al usuario.
        """

        query = (
            select(UserRole)
            .where(UserRole.user_id == user_id)
            .options(selectinload(UserRole.role))
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def get_user_role(self, user_id: int, role_id: int) -> UserRole | None:
        """Obtiene una asignacion usuario-rol existente.

        Args:
            user_id: Identificador entero del usuario.
            role_id: Identificador entero del rol.

        Returns:
            La entidad `UserRole` si existe; `None` si no se encuentra.
        """

        query = (
            select(UserRole)
            .where(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id,
            )
            .options(selectinload(UserRole.role))
        )
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def assign_role(self, user_role: UserRole) -> UserRole:
        """Persiste una asignacion de rol.

        Args:
            user_role: Entidad `UserRole` a crear.

        Returns:
            La misma entidad `UserRole` persistida y refrescada.
        """

        self.db.add(user_role)
        await self.db.commit()
        await self.db.refresh(user_role)

        return user_role

    async def remove_role(self, user_role: UserRole) -> None:
        """Elimina una asignacion de rol.

        Args:
            user_role: Entidad `UserRole` a eliminar.
        """

        await self.db.delete(user_role)
        await self.db.commit()
