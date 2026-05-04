"""Dependencias de autorización basadas en roles.

Este módulo expone `require_roles`, un generador de dependencias de FastAPI que
verifica si el usuario autenticado posee al menos uno de los roles permitidos.
"""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.modules.auth.dependencies.auth_dependency import get_current_user
from app.modules.auth.models.user_model import User


def require_roles(allowed_roles: list[str]) -> Callable[..., Awaitable[User]]:
    """Crea una dependencia que exige uno o más roles.

    El verificador obtiene el usuario actual mediante `get_current_user` y
    compara los roles asociados con la lista de roles permitidos.

    Args:
        allowed_roles: Lista de nombres de roles que autorizan el acceso.

    Returns:
        Una función asíncrona (dependencia) que retorna el `User` si está
        autorizado.

    Raises:
        HTTPException: Con código 403 si el usuario no posee roles suficientes.
    """
    
    async def role_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        """Verifica roles del usuario autenticado.

        Args:
            current_user: Usuario autenticado inyectado por `get_current_user`.

        Returns:
            El mismo `current_user` si está autorizado.

        Raises:
            HTTPException: Con código 403 si el usuario no tiene permisos.
        """

        user_roles = [user_role.role.name for user_role in current_user.roles]

        has_permission = any(role in allowed_roles for role in user_roles)

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        return current_user
    
    return role_checker
