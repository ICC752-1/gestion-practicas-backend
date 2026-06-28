"""Servicios de negocio para usuarios.

Este modulo define `UserService`, encargado de coordinar casos de uso
relacionados con usuarios y delegar operaciones de persistencia a los
repositorios correspondientes.
"""

import logging
import secrets

from app.modules.auth.models.user_model import User
from app.modules.auth.repositories.user_repository import UserRepository
from app.modules.auth.services.password_service import PasswordService
from app.modules.auth.utils.normalization import normalize_phone, normalize_rut
from app.modules.auth.schemas.user_schema import UserCreateRequest, UserUpdateRequest


logger = logging.getLogger(__name__)


class UserService:
    """Orquesta casos de uso relacionados con usuarios.

    Attributes:
        user_repository: Repositorio de acceso a datos para usuarios.
        password_service: Servicio de hashing de contrasenas.
    """

    def __init__(
        self,
        user_repository: UserRepository,
        password_service: PasswordService,
    ) -> None:
        """Inicializa el servicio con sus dependencias.

        Args:
            user_repository: Repositorio para consultar y persistir usuarios.
            password_service: Servicio para hashear contrasenas.
        """

        self.user_repository = user_repository
        self.password_service = password_service

    async def create_user(self, payload: UserCreateRequest) -> User:
        """Crea un usuario con password hasheada.

        Normaliza RUT y telefonos antes de persistir.

        Args:
            payload: Datos validados para crear el usuario.

        Returns:
            Entidad `User` persistida.
        """

        initial_password = payload.password or secrets.token_urlsafe(32)
        hashed_password = self.password_service.hash_password(initial_password)

        user = User(
            email=payload.email,
            password_hash=hashed_password,
            first_name=payload.first_name,
            last_name=payload.last_name,
            rut=normalize_rut(payload.rut),
            degree=payload.degree,
            cod_degree=payload.cod_degree,
            admission_year=payload.admission_year,
            sexo=payload.sexo,
            phone=normalize_phone(payload.phone) if payload.phone else None,
            profession=payload.profession,
            position=payload.position,
            departament=payload.departament,
            sup_phone=normalize_phone(payload.sup_phone) if payload.sup_phone else None,
            is_active=True,
            is_verified=False,
            must_change_password=True,
        )
        user = await self.user_repository.create_user(user)

        logger.info(
            "User created",
            extra={"user_id": user.id},
        )

        return user

    async def list_users(
        self,
        is_active: bool | None = None,
        email: str | None = None,
        search: str | None = None,
        role_name: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> list[User]:
        """Lista usuarios con filtros opcionales.

        Args:
            is_active: Filtra por estado de activacion si se especifica.
            email: Filtra por correo exacto si se especifica.

        Returns:
            Lista de entidades `User`.
        """

        return await self.user_repository.list_users(
            is_active=is_active,
            email=email,
            search=search,
            role_name=role_name,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )

    async def count_users(
        self,
        is_active: bool | None = None,
        email: str | None = None,
        search: str | None = None,
        role_name: str | None = None,
    ) -> int:
        """Cuenta usuarios con filtros administrativos."""

        return await self.user_repository.count_users(
            is_active=is_active,
            email=email,
            search=search,
            role_name=role_name,
        )

    async def update_user(self, user: User, payload: UserUpdateRequest) -> User:
        """Actualiza un usuario con los campos permitidos.

        Normaliza RUT y telefonos si se envian en el payload.

        Args:
            user: Entidad `User` a modificar.
            payload: Datos validados de actualizacion.

        Returns:
            Entidad `User` actualizada.
        """

        update_data = payload.model_dump(exclude_unset=True, exclude_none=True)

        updated_fields = list(update_data.keys())

        if "rut" in update_data:
            update_data["rut"] = normalize_rut(update_data["rut"])

        if "phone" in update_data:
            update_data["phone"] = normalize_phone(update_data["phone"])

        if "sup_phone" in update_data:
            update_data["sup_phone"] = normalize_phone(update_data["sup_phone"])

        for field_name, value in update_data.items():
            setattr(user, field_name, value)
        user = await self.user_repository.update_user(user)

        logger.info(
            "User updated",
            extra={"user_id": user.id, "fields": updated_fields},
        )

        return user
