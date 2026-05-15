"""Repositorio de acceso a datos para roles.

Este modulo define `RoleRepository`, encargado de encapsular consultas y
operaciones de persistencia relacionadas con la entidad `Role` usando una sesion
asincrona de SQLAlchemy.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.role_model import Role


class RoleRepository:
    """Implementa operaciones de lectura y escritura sobre roles.

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

    async def list_roles(self) -> list[Role]:
        """Lista todos los roles existentes.

        Returns:
            Lista de entidades `Role`.
        """

        query = select(Role).order_by(Role.id)
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def get_role_by_id(self, role_id: int) -> Role | None:
        """Obtiene un rol por identificador.

        Args:
            role_id: Identificador entero del rol.

        Returns:
            La entidad `Role` si existe; `None` si no se encuentra.
        """

        query = select(Role).where(Role.id == role_id)
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def get_role_by_name(self, role_name: str) -> Role | None:
        """Obtiene un rol por nombre.

        Args:
            role_name: Nombre del rol (segun enumRole).

        Returns:
            La entidad `Role` si existe; `None` si no se encuentra.
        """

        query = select(Role).where(Role.name == role_name)
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def update_role(self, role: Role) -> Role:
        """Actualiza un rol existente en la base de datos.

        Args:
            role: Entidad `Role` con cambios ya aplicados.

        Returns:
            La entidad `Role` actualizada y refrescada.
        """

        await self.db.commit()
        await self.db.refresh(role)

        return role
