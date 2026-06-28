"""Controlador HTTP para gestion de usuarios.

Este modulo define las rutas administrativas relacionadas con creacion,
consulta y actualizacion de usuarios.
"""

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import config
from app.core.database.database import get_db
from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.auth.models.account_activation_token_model import (
    AccountActivationToken,
)
from app.modules.auth.models.user_model import User
from app.modules.auth.repositories.account_activation_token_repository import (
    AccountActivationTokenRepository,
)
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
from app.modules.auth.services.token_service import TokenService
from app.modules.auth.services.user_service import UserService
from app.modules.auth.utils.roles import (
    STUDENT_ACCOUNT_MANAGER_ROLES,
    STUDENT_ROLE,
    SUPERADMIN_ROLE,
    USER_ADMIN_ROLES,
)
from app.modules.notifications.repositories.notification_repository import (
    NotificationRepository,
)
from app.modules.notifications.services.notification_service import NotificationService
from app.modules.notifications.utils.notification_event_helpers import (
    build_user_activation_notification,
)

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


def _build_notification_service(db: AsyncSession) -> NotificationService:
    return NotificationService(
        notification_repository=NotificationRepository(db),
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


def _ensure_student_scope(user: User) -> None:
    roles = set(_role_names(user))
    if STUDENT_ROLE not in roles or roles - {STUDENT_ROLE}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only student accounts can be managed from this endpoint",
        )


async def _ensure_unique_user_identity(
    *,
    payload: UserCreateRequest,
    user_repository: UserRepository,
    actor_id: int,
) -> None:
    existing_email = await user_repository.get_user_by_email(payload.email)
    if existing_email:
        logger.warning(
            "Create user failed: email already exists",
            extra={"actor_id": actor_id},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        )

    existing_rut = await user_repository.get_user_by_rut(payload.rut)
    if existing_rut:
        logger.warning(
            "Create user failed: RUT already exists",
            extra={"actor_id": actor_id},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="RUT already exists",
        )


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


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _build_activation_url(raw_token: str) -> str:
    frontend_base_url = config.FRONTEND_BASE_URL.rstrip("/")

    return f"{frontend_base_url}/activar-cuenta?token={quote(raw_token, safe='')}"


async def _create_account_activation_link(
    *,
    activation_token_repository: AccountActivationTokenRepository,
    user: User,
    actor: User,
    token_service: TokenService,
) -> tuple[str, datetime]:
    """Genera un enlace de activacion de un solo uso para el usuario creado."""

    await activation_token_repository.revoke_active_tokens_for_user(user.id)

    raw_token = secrets.token_urlsafe(32)
    expires_at = _utc_now() + timedelta(
        hours=config.USER_ACTIVATION_TOKEN_EXPIRE_HOURS
    )
    await activation_token_repository.create_token(
        AccountActivationToken(
            user_id=user.id,
            token_hash=token_service.hash_token(raw_token),
            expires_at=expires_at,
            created_by_id=actor.id,
        )
    )

    return _build_activation_url(raw_token), expires_at


async def _dispatch_account_activation_notification(
    *,
    notification_service: NotificationService,
    user: User,
    activation_url: str,
    expires_at: datetime,
) -> None:
    """Notifica al usuario creado su enlace de activacion sin bloquear el alta."""

    notification = build_user_activation_notification(
        recipient_user_id=user.id,
        recipient_email=user.email,
        activation_url=activation_url,
        expires_at=expires_at,
    )

    try:
        await notification_service.create_and_dispatch(notification)
    except Exception:
        logger.warning(
            "Fallo al despachar enlace de activacion para usuario creado. "
            "El alta continua normalmente.",
            extra={"user_id": user.id},
            exc_info=True,
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

    await _ensure_unique_user_identity(
        payload=payload,
        user_repository=user_repository,
        actor_id=current_user.id,
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

    activation_url, activation_expires_at = await _create_account_activation_link(
        activation_token_repository=AccountActivationTokenRepository(db),
        user=user,
        actor=current_user,
        token_service=TokenService(),
    )

    await _dispatch_account_activation_notification(
        notification_service=_build_notification_service(db),
        user=user,
        activation_url=activation_url,
        expires_at=activation_expires_at,
    )

    logger.info(
        "User created",
        extra={"actor_id": current_user.id, "user_id": user.id},
    )

    return _admin_response(user)


@router.get("/students", response_model=UserListResponse)
async def list_student_accounts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(STUDENT_ACCOUNT_MANAGER_ROLES))],
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: Literal[
        "id",
        "created_at",
        "first_name",
        "last_name",
        "email",
        "rut",
        "is_active",
    ] = Query(default="created_at"),
    sort_dir: Literal["asc", "desc"] = Query(default="desc"),
) -> UserListResponse:
    """Lista cuentas de estudiantes para gestion academica acotada."""

    logger.info(
        "List student accounts request received",
        extra={"actor_id": current_user.id, "is_active_filter": is_active},
    )
    service = _build_service(db)
    users = await service.list_users(
        is_active=is_active,
        search=search,
        role_name=STUDENT_ROLE,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    total = await service.count_users(
        is_active=is_active,
        search=search,
        role_name=STUDENT_ROLE,
    )

    return UserListResponse(
        items=[_admin_response(user) for user in users],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/students",
    response_model=UserAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_student_account(
    payload: UserCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(STUDENT_ACCOUNT_MANAGER_ROLES))],
) -> UserAdminResponse:
    """Crea una cuenta con rol Estudiante sin conceder permisos administrativos."""

    logger.info(
        "Create student account request received",
        extra={"actor_id": current_user.id},
    )
    user_repository = UserRepository(db)
    await _ensure_unique_user_identity(
        payload=payload,
        user_repository=user_repository,
        actor_id=current_user.id,
    )

    service = _build_service(db)
    user = await service.create_user(payload.model_copy(update={"role_ids": []}))

    student_role = await RoleRepository(db).get_role_by_name(STUDENT_ROLE)
    if not student_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student role not found",
        )

    await _build_role_service(db).assign_role(user=user, role=student_role)
    refreshed_user = await user_repository.get_user_by_id(user.id)
    if refreshed_user:
        user = refreshed_user

    activation_url, activation_expires_at = await _create_account_activation_link(
        activation_token_repository=AccountActivationTokenRepository(db),
        user=user,
        actor=current_user,
        token_service=TokenService(),
    )

    await _dispatch_account_activation_notification(
        notification_service=_build_notification_service(db),
        user=user,
        activation_url=activation_url,
        expires_at=activation_expires_at,
    )

    logger.info(
        "Student account created",
        extra={"actor_id": current_user.id, "user_id": user.id},
    )

    return _admin_response(user)


@router.patch("/students/{user_id}", response_model=UserAdminResponse)
async def update_student_account(
    user_id: int,
    payload: UserUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(STUDENT_ACCOUNT_MANAGER_ROLES))],
) -> UserAdminResponse:
    """Actualiza datos basicos o estado de una cuenta exclusivamente estudiantil."""

    user_repository = UserRepository(db)
    user = await user_repository.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    _ensure_student_scope(user)

    if payload.rut:
        existing_rut = await user_repository.get_user_by_rut(payload.rut)
        if existing_rut and existing_rut.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="RUT already exists",
            )

    service = _build_service(db)
    user = await service.update_user(user, payload)

    if payload.is_active is False:
        revoked_count = await RefreshTokenRepository(db).revoke_active_tokens_for_user(
            user_id,
        )
        logger.info(
            "Refresh tokens revoked after student deactivation",
            extra={"actor_id": current_user.id, "user_id": user_id, "count": revoked_count},
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
    sort_by: Literal[
        "id",
        "created_at",
        "first_name",
        "last_name",
        "email",
        "rut",
        "is_active",
    ] = Query(default="created_at"),
    sort_dir: Literal["asc", "desc"] = Query(default="desc"),
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
            "sort_by": sort_by,
            "sort_dir": sort_dir,
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
        sort_by=sort_by,
        sort_dir=sort_dir,
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
