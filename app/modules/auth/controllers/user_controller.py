"""Controlador HTTP para gestion de usuarios.

Este modulo define las rutas administrativas relacionadas con creacion,
consulta y actualizacion de usuarios.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.database import get_db
from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.auth.models.user_model import User
from app.modules.auth.repositories.refresh_token_repository import RefreshTokenRepository
from app.modules.auth.repositories.role_repository import RoleRepository
from app.modules.auth.repositories.user_repository import UserRepository
from app.modules.auth.repositories.user_role_repository import UserRoleRepository
from app.modules.auth.schemas.rol_schema import AssignRoleRequest, UserRoleResponse
from app.modules.auth.schemas.user_schema import (
    UserAdminResponse,
    UserCreateRequest,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
)
from app.modules.auth.services.password_service import PasswordService
from app.modules.auth.services.role_service import RoleService
from app.modules.auth.services.user_service import UserService
from app.modules.auth.utils.roles import SUPERADMIN_ROLE, USER_ADMIN_ROLES

router = APIRouter(prefix="/users", tags=["Users"])
logger = logging.getLogger(__name__)


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


def _role_names(user: User) -> list[str]:
    return [user_role.role.name for user_role in user.roles]


def _admin_response(user: User) -> UserAdminResponse:
    return UserAdminResponse(
        **UserResponse.model_validate(user).model_dump(),
        roles=_role_names(user),
    )


def _has_role(user: User, role_name: str) -> bool:
    return role_name in _role_names(user)


async def _ensure_can_remove_superadmin_access(
    *,
    actor: User,
    target: User,
    user_repository: UserRepository,
) -> None:
    if actor.id == target.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Superadmin cannot remove own administration access",
        )

    if target.is_active and _has_role(target, SUPERADMIN_ROLE):
        active_superadmins = await user_repository.count_active_users_with_role(
            SUPERADMIN_ROLE,
        )
        if active_superadmins <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot remove the last active Superadmin",
            )


@router.post("", response_model=UserAdminResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(USER_ADMIN_ROLES))],
) -> UserAdminResponse:
    """Crea un usuario nuevo.

    Requiere roles administrativos. Valida unicidad de email y RUT antes de
    persistir el usuario.

    Args:
        payload: Datos validados del usuario a crear.
        db: Sesion asincrona de base de datos.
        current_user: Usuario administrador autenticado.

    Returns:
        `UserResponse` con el usuario creado.

    Raises:
        HTTPException: 409 si el email o RUT ya existen.
    """
    logger.info("Create user request received", extra={"actor_id": current_user.id})
    user_repository = UserRepository(db)

    existing_email = await user_repository.get_user_by_email(payload.email)
    if existing_email:
        logger.warning(
            "Create user failed: email already exists",
            extra={"actor_id": current_user.id},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        )

    existing_rut = await user_repository.get_user_by_rut(payload.rut)
    if existing_rut:
        logger.warning(
            "Create user failed: RUT already exists",
            extra={"actor_id": current_user.id},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="RUT already exists",
        )

    role_repository = RoleRepository(db)
    roles_to_assign = []
    for role_id in set(payload.role_ids):
        role = await role_repository.get_role_by_id(role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found",
            )
        roles_to_assign.append(role)

    service = _build_service(db)
    user = await service.create_user(payload)

    if roles_to_assign:
        role_service = _build_role_service(db)
        for role in roles_to_assign:
            await role_service.assign_role(user=user, role=role)

        refreshed_user = await user_repository.get_user_by_id(user.id)
        if refreshed_user:
            user = refreshed_user

    logger.info(
        "User created",
        extra={"actor_id": current_user.id, "user_id": user.id},
    )

    return _admin_response(user)


@router.get("", response_model=UserListResponse)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(USER_ADMIN_ROLES))],
    is_active: bool | None = Query(default=None),
    email: str | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    role: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> UserListResponse:
    """Lista usuarios con filtros opcionales.

    Requiere roles administrativos. Permite filtrar por estado y correo exacto.

    Args:
        db: Sesion asincrona de base de datos.
        current_user: Usuario administrador autenticado.
        is_active: Filtra por estado de activacion si se especifica.
        email: Filtra por correo exacto si se especifica.

    Returns:
        Lista de `UserResponse`.
    """
    logger.info(
        "List users request received",
        extra={
            "actor_id": current_user.id,
            "is_active_filter": is_active,
            "has_email_filter": bool(email),
        },
    )
    service = _build_service(db)
    users = await service.list_users(
        is_active=is_active,
        email=email,
        search=search,
        role_name=role,
        limit=limit,
        offset=offset,
    )
    total = await service.count_users(
        is_active=is_active,
        email=email,
        search=search,
        role_name=role,
    )

    logger.info(
        "List users completed",
        extra={"actor_id": current_user.id, "count": len(users)},
    )

    return UserListResponse(
        items=[_admin_response(user) for user in users],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{user_id}", response_model=UserAdminResponse)
async def get_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(USER_ADMIN_ROLES))],
) -> UserAdminResponse:
    """Obtiene un usuario por identificador.

    Requiere roles administrativos.

    Args:
        user_id: Identificador entero del usuario.
        db: Sesion asincrona de base de datos.
        current_user: Usuario administrador autenticado.

    Returns:
        `UserResponse` con los datos del usuario.

    Raises:
        HTTPException: 404 si el usuario no existe.
    """
    logger.info(
        "Get user request received",
        extra={"actor_id": current_user.id, "user_id": user_id},
    )
    user_repository = UserRepository(db)
    user = await user_repository.get_user_by_id(user_id)

    if not user:
        logger.warning(
            "Get user failed: user not found",
            extra={"actor_id": current_user.id, "user_id": user_id},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    logger.info(
        "Get user completed",
        extra={"actor_id": current_user.id, "user_id": user_id},
    )

    return _admin_response(user)


@router.patch("/{user_id}", response_model=UserAdminResponse)
async def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(USER_ADMIN_ROLES))],
) -> UserAdminResponse:
    """Actualiza datos de un usuario.

    Requiere roles administrativos. Solo se modifican los campos enviados.

    Args:
        user_id: Identificador entero del usuario.
        payload: Datos parciales a actualizar.
        db: Sesion asincrona de base de datos.
        current_user: Usuario administrador autenticado.

    Returns:
        `UserResponse` con el usuario actualizado.

    Raises:
        HTTPException: 404 si el usuario no existe.
    """
    logger.info(
        "Update user request received",
        extra={"actor_id": current_user.id, "user_id": user_id},
    )
    user_repository = UserRepository(db)
    user = await user_repository.get_user_by_id(user_id)

    if not user:
        logger.warning(
            "Update user failed: user not found",
            extra={"actor_id": current_user.id, "user_id": user_id},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if payload.rut:
        existing_rut = await user_repository.get_user_by_rut(payload.rut)
        if existing_rut and existing_rut.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="RUT already exists",
            )

    if payload.is_active is False and user.is_active:
        await _ensure_can_remove_superadmin_access(
            actor=current_user,
            target=user,
            user_repository=user_repository,
        )

    service = _build_service(db)
    user = await service.update_user(user, payload)

    if payload.is_active is False:
        revoked_count = await RefreshTokenRepository(db).revoke_active_tokens_for_user(
            user_id,
        )
        logger.info(
            "Refresh tokens revoked after user deactivation",
            extra={"actor_id": current_user.id, "user_id": user_id, "count": revoked_count},
        )

    logger.info(
        "User updated",
        extra={"actor_id": current_user.id, "user_id": user_id},
    )

    return _admin_response(user)


@router.get("/{user_id}/roles", response_model=list[UserRoleResponse])
async def list_user_roles(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(USER_ADMIN_ROLES))],
) -> list[UserRoleResponse]:
    """Lista los roles asociados a un usuario.

    Requiere roles administrativos.

    Args:
        user_id: Identificador entero del usuario.
        db: Sesion asincrona de base de datos.
        current_user: Usuario administrador autenticado.

    Returns:
        Lista de `UserRoleResponse`.

    Raises:
        HTTPException: 404 si el usuario no existe.
    """
    logger.info(
        "List user roles request received",
        extra={"actor_id": current_user.id, "user_id": user_id},
    )
    user_repository = UserRepository(db)
    user = await user_repository.get_user_by_id(user_id)

    if not user:
        logger.warning(
            "List user roles failed: user not found",
            extra={"actor_id": current_user.id, "user_id": user_id},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    logger.info(
        "List user roles completed",
        extra={"actor_id": current_user.id, "user_id": user_id, "count": len(user.roles)},
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
    current_user: Annotated[User, Depends(require_roles(USER_ADMIN_ROLES))],
) -> UserRoleResponse:
    """Asigna un rol a un usuario.

    Requiere roles administrativos.

    Args:
        user_id: Identificador entero del usuario.
        payload: Identificador del rol a asignar.
        db: Sesion asincrona de base de datos.
        current_user: Usuario administrador autenticado.

    Returns:
        `UserRoleResponse` con el rol asignado.

    Raises:
        HTTPException: 404 si el usuario o rol no existen.
        HTTPException: 409 si el rol ya esta asignado.
    """
    logger.info(
        "Assign user role request received",
        extra={"actor_id": current_user.id, "user_id": user_id, "role_id": payload.role_id},
    )
    user_repository = UserRepository(db)
    role_repository = RoleRepository(db)
    user_role_repository = UserRoleRepository(db)

    user = await user_repository.get_user_by_id(user_id)
    if not user:
        logger.warning(
            "Assign role failed: user not found",
            extra={"actor_id": current_user.id, "user_id": user_id},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    role = await role_repository.get_role_by_id(payload.role_id)
    if not role:
        logger.warning(
            "Assign role failed: role not found",
            extra={"actor_id": current_user.id, "role_id": payload.role_id},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    existing = await user_role_repository.get_user_role(
        user_id=user_id,
        role_id=payload.role_id,
    )
    if existing:
        logger.info(
            "Assign role skipped: role already assigned",
            extra={"actor_id": current_user.id, "user_id": user_id, "role_id": payload.role_id},
        )
        return UserRoleResponse.model_validate(role)

    service = _build_role_service(db)
    await service.assign_role(user=user, role=role)

    logger.info(
        "Role assigned to user",
        extra={"actor_id": current_user.id, "user_id": user_id, "role_id": role.id},
    )

    return UserRoleResponse.model_validate(role)


@router.delete(
    "/{user_id}/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_user_role(
    user_id: int,
    role_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(USER_ADMIN_ROLES))],
) -> None:
    """Elimina un rol asociado a un usuario.

    Requiere roles administrativos.

    Args:
        user_id: Identificador entero del usuario.
        role_id: Identificador entero del rol.
        db: Sesion asincrona de base de datos.
        current_user: Usuario administrador autenticado.

    Returns:
        Respuesta vacia con codigo 204.

    Raises:
        HTTPException: 404 si el usuario o la asignacion no existen.
    """
    logger.info(
        "Remove user role request received",
        extra={"actor_id": current_user.id, "user_id": user_id, "role_id": role_id},
    )
    user_repository = UserRepository(db)
    user = await user_repository.get_user_by_id(user_id)

    if not user:
        logger.warning(
            "Remove role failed: user not found",
            extra={"actor_id": current_user.id, "user_id": user_id},
        )
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
        logger.info(
            "Remove role skipped: role assignment not found",
            extra={"actor_id": current_user.id, "user_id": user_id, "role_id": role_id},
        )
        return None

    if user_role.role.name == SUPERADMIN_ROLE:
        await _ensure_can_remove_superadmin_access(
            actor=current_user,
            target=user,
            user_repository=user_repository,
        )

    service = _build_role_service(db)
    await service.remove_role(user_role)

    logger.info(
        "Role removed from user",
        extra={"actor_id": current_user.id, "user_id": user_id, "role_id": role_id},
    )

    return None
