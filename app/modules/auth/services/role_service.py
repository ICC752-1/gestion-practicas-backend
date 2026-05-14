"""Servicios de negocio para roles y asignaciones.

Este modulo define `RoleService`, encargado de coordinar casos de uso
relacionados con roles y asignaciones usuario-rol.
"""

from app.modules.auth.models.role_model import Role
from app.modules.auth.models.user_model import User
from app.modules.auth.models.user_role_model import UserRole
from app.modules.auth.repositories.role_repository import RoleRepository
from app.modules.auth.repositories.user_role_repository import UserRoleRepository
from app.modules.auth.schemas.rol_schema import RoleUpdateRequest


class RoleService:
    """Orquesta casos de uso relacionados con roles.

    Attributes:
        role_repository: Repositorio de acceso a datos para roles.
        user_role_repository: Repositorio de asignaciones usuario-rol.
    """

    def __init__(
        self,
        role_repository: RoleRepository,
        user_role_repository: UserRoleRepository,
    ) -> None:
        """Inicializa el servicio con sus dependencias.

        Args:
            role_repository: Repositorio para consultar roles.
            user_role_repository: Repositorio para asignaciones de roles.
        """

        self.role_repository = role_repository
        self.user_role_repository = user_role_repository

    async def list_roles(self) -> list[Role]:
        """Lista todos los roles existentes.

        Returns:
            Lista de entidades `Role`.
        """

        return await self.role_repository.list_roles()

    async def update_role(self, role: Role, payload: RoleUpdateRequest) -> Role:
        """Actualiza la descripcion de un rol.

        Args:
            role: Entidad `Role` a modificar.
            payload: Datos validados de actualizacion.

        Returns:
            Entidad `Role` actualizada.
        """

        update_data = payload.model_dump(exclude_unset=True, exclude_none=True)

        for field_name, value in update_data.items():
            setattr(role, field_name, value)

        return await self.role_repository.update_role(role)

    async def list_roles_for_user(self, user_id: int) -> list[UserRole]:
        """Lista roles asociados a un usuario.

        Args:
            user_id: Identificador entero del usuario.

        Returns:
            Lista de asignaciones `UserRole`.
        """

        return await self.user_role_repository.list_roles_for_user(user_id)

    async def assign_role(self, user: User, role: Role) -> UserRole:
        """Asigna un rol a un usuario.

        Args:
            user: Entidad `User`.
            role: Entidad `Role`.

        Returns:
            Entidad `UserRole` creada.
        """

        user_role = UserRole(user_id=user.id, role_id=role.id)
        return await self.user_role_repository.assign_role(user_role)

    async def remove_role(self, user_role: UserRole) -> None:
        """Elimina una asignacion de rol.

        Args:
            user_role: Entidad `UserRole` a eliminar.
        """

        await self.user_role_repository.remove_role(user_role)
