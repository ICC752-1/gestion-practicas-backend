"""Controlador HTTP para gestion de usuarios.

Este modulo define las rutas administrativas relacionadas con creacion,
consulta y actualizacion de usuarios.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.database import get_db
from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.auth.models.user_model import User
from app.modules.auth.repositories.role_repository import RoleRepository
from app.modules.auth.repositories.user_repository import UserRepository
from app.modules.auth.repositories.user_role_repository import UserRoleRepository
from app.modules.auth.schemas.rol_schema import AssignRoleRequest, UserRoleResponse
from app.modules.auth.schemas.user_schema import (
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from app.modules.auth.services.password_service import PasswordService
from app.modules.auth.services.role_service import RoleService
from app.modules.auth.services.user_service import UserService

ADMIN_ROLES = [
    "Supervisor de practica",
    "Encargado de practica",
    "Director de carrera",
    "Secretaria de Carrera",
]

router = APIRouter(prefix="/users", tags=["Users"])


def _build_service(db: AsyncSession) -> UserService:
    return UserService(
        user_repository=UserRepository(db),
        password_service=PasswordService(),
    )


def _build_role_service(db: AsyncSession) -> RoleService:
    return RoleService(
        role_repository=RoleRepository(db),
        user_role_repository=UserRoleRepository(db),
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(ADMIN_ROLES))],
) -> UserResponse:
    user_repository = UserRepository(db)

    existing_email = await user_repository.get_user_by_email(payload.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        )

    existing_rut = await user_repository.get_user_by_rut(payload.rut)
    if existing_rut:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="RUT already exists",
        )

    service = _build_service(db)
    user = await service.create_user(payload)

    return UserResponse.model_validate(user)


@router.get("", response_model=list[UserResponse])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(ADMIN_ROLES))],
    is_active: bool | None = Query(default=None),
    email: str | None = Query(default=None),
) -> list[UserResponse]:
    service = _build_service(db)
    users = await service.list_users(is_active=is_active, email=email)

    return [UserResponse.model_validate(user) for user in users]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(ADMIN_ROLES))],
) -> UserResponse:
    user_repository = UserRepository(db)
    user = await user_repository.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(ADMIN_ROLES))],
) -> UserResponse:
    user_repository = UserRepository(db)
    user = await user_repository.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    service = _build_service(db)
    user = await service.update_user(user, payload)

    return UserResponse.model_validate(user)


@router.get("/{user_id}/roles", response_model=list[UserRoleResponse])
async def list_user_roles(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(ADMIN_ROLES))],
) -> list[UserRoleResponse]:
    user_repository = UserRepository(db)
    user = await user_repository.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return [
        UserRoleResponse.model_validate(user_role.role)
        for user_role in user.roles
    ]


@router.post(
    "/{user_id}/roles",
    response_model=UserRoleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_user_role(
    user_id: int,
    payload: AssignRoleRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(ADMIN_ROLES))],
) -> UserRoleResponse:
    user_repository = UserRepository(db)
    role_repository = RoleRepository(db)
    user_role_repository = UserRoleRepository(db)

    user = await user_repository.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    role = await role_repository.get_role_by_id(payload.role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    existing = await user_role_repository.get_user_role(
        user_id=user_id,
        role_id=payload.role_id,
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role already assigned to user",
        )

    service = _build_role_service(db)
    await service.assign_role(user=user, role=role)

    return UserRoleResponse.model_validate(role)


@router.delete(
    "/{user_id}/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_user_role(
    user_id: int,
    role_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(ADMIN_ROLES))],
) -> None:
    user_repository = UserRepository(db)
    user = await user_repository.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user_role_repository = UserRoleRepository(db)
    user_role = await user_role_repository.get_user_role(
        user_id=user_id,
        role_id=role_id,
    )

    if not user_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role assignment not found",
        )

    service = _build_role_service(db)
    await service.remove_role(user_role)

    return None
