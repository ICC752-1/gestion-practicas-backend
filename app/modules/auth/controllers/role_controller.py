"""Controlador HTTP para gestion de roles y asignaciones.

Este modulo define rutas administrativas para consultar roles y asignarlos a
usuarios.
"""

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


def _build_service(db: AsyncSession) -> RoleService:
    return RoleService(
        role_repository=RoleRepository(db),
        user_role_repository=UserRoleRepository(db),
    )


@router.get("", response_model=list[RoleResponse])
async def list_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(ADMIN_ROLES))],
) -> list[RoleResponse]:
    service = _build_service(db)
    roles = await service.list_roles()

    return [RoleResponse.model_validate(role) for role in roles]


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(ADMIN_ROLES))],
) -> RoleResponse:
    role_repository = RoleRepository(db)
    role = await role_repository.get_role_by_id(role_id)

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    return RoleResponse.model_validate(role)


@router.patch("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    payload: RoleUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(ADMIN_ROLES))],
) -> RoleResponse:
    role_repository = RoleRepository(db)
    role = await role_repository.get_role_by_id(role_id)

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    service = _build_service(db)
    role = await service.update_role(role, payload)

    return RoleResponse.model_validate(role)
