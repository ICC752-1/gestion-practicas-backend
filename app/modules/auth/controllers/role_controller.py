"""Controlador HTTP para gestion de roles y asignaciones.

Este modulo define rutas administrativas para consultar roles y asignarlos a
usuarios.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.database import get_db
from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.auth.models.user_model import User
from app.modules.auth.repositories.role_repository import RoleRepository
from app.modules.auth.repositories.user_role_repository import UserRoleRepository
from app.modules.auth.schemas.rol_schema import (
    RoleResponse,
    RoleUpdateRequest,
)
from app.modules.auth.services.role_service import RoleService

ADMIN_ROLES = [
    "Supervisor de practica",
    "Encargado de practica",
    "Director de carrera",
    "Secretaria de Carrera",
]

router = APIRouter(prefix="/roles", tags=["Roles"])
logger = logging.getLogger(__name__)


def _build_service(db: AsyncSession) -> RoleService:
    return RoleService(
        role_repository=RoleRepository(db),
        user_role_repository=UserRoleRepository(db),
    )


@router.get("", response_model=list[RoleResponse])
async def list_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(ADMIN_ROLES))],
) -> list[RoleResponse]:
    """Lista todos los roles existentes.

    Requiere roles administrativos.

    Args:
        db: Sesion asincrona de base de datos.
        current_user: Usuario administrador autenticado.

    Returns:
        Lista de `RoleResponse`.
    """
    logger.info(
        "List roles request received",
        extra={"actor_id": current_user.id},
    )
    service = _build_service(db)
    roles = await service.list_roles()

    logger.info(
        "List roles completed",
        extra={"actor_id": current_user.id, "count": len(roles)},
    )

    return [RoleResponse.model_validate(role) for role in roles]


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(ADMIN_ROLES))],
) -> RoleResponse:
    """Obtiene un rol por identificador.

    Requiere roles administrativos.

    Args:
        role_id: Identificador entero del rol.
        db: Sesion asincrona de base de datos.
        current_user: Usuario administrador autenticado.

    Returns:
        `RoleResponse` con los datos del rol.

    Raises:
        HTTPException: 404 si el rol no existe.
    """
    logger.info(
        "Get role request received",
        extra={"actor_id": current_user.id, "role_id": role_id},
    )
    role_repository = RoleRepository(db)
    role = await role_repository.get_role_by_id(role_id)

    if not role:
        logger.warning(
            "Get role failed: role not found",
            extra={"actor_id": current_user.id, "role_id": role_id},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    logger.info(
        "Get role completed",
        extra={"actor_id": current_user.id, "role_id": role_id},
    )

    return RoleResponse.model_validate(role)


@router.patch("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    payload: RoleUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(ADMIN_ROLES))],
) -> RoleResponse:
    """Actualiza la descripcion de un rol.

    Requiere roles administrativos.

    Args:
        role_id: Identificador entero del rol.
        payload: Datos parciales de actualizacion.
        db: Sesion asincrona de base de datos.
        current_user: Usuario administrador autenticado.

    Returns:
        `RoleResponse` con el rol actualizado.

    Raises:
        HTTPException: 404 si el rol no existe.
    """
    logger.info(
        "Update role request received",
        extra={"actor_id": current_user.id, "role_id": role_id},
    )
    role_repository = RoleRepository(db)
    role = await role_repository.get_role_by_id(role_id)

    if not role:
        logger.warning(
            "Update role failed: role not found",
            extra={"actor_id": current_user.id, "role_id": role_id},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    service = _build_service(db)
    role = await service.update_role(role, payload)

    logger.info(
        "Role updated",
        extra={"actor_id": current_user.id, "role_id": role_id},
    )

    return RoleResponse.model_validate(role)
