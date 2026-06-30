"""Repositorio de acceso a datos para usuarios.

Este módulo define `UserRepository`, encargado de encapsular consultas y
operaciones de persistencia relacionadas con la entidad `User` usando una sesión
asíncrona de SQLAlchemy.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models.user_model import User
from app.modules.auth.models.user_role_model import UserRole
from app.modules.auth.models.role_model import Role
from app.modules.internships.models.internship_model import Internship
from app.modules.internships.models.student_internship_requirement_model import (
    StudentInternshipRequirement,
)

USER_SORT_COLUMNS = {
    "id": User.id,
    "created_at": User.created_at,
    "first_name": User.first_name,
    "last_name": User.last_name,
    "email": User.email,
    "rut": User.rut,
    "enrollment": User.enrollment,
    "admission_year": User.admission_year,
    "is_active": User.is_active,
}


class UserRepository:
    """Implementa operaciones de lectura y escritura sobre usuarios.

    Attributes:
        db: Sesión asíncrona (`AsyncSession`) utilizada para ejecutar consultas y
            confirmar transacciones.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el repositorio con una sesión de base de datos.

        Args:
            db: Sesión asíncrona de SQLAlchemy.
        """

        self.db = db
    
    async def get_user_by_email(self, email:str) -> User | None:
        """Obtiene un usuario por correo electrónico.

        La consulta incluye carga ansiosa de roles asociados (`User.roles`) y de
        la relación hacia `Role` a través de `UserRole`.

        Args:
            email: Correo electrónico a buscar.

        Returns:
            La entidad `User` si existe; `None` si no se encuentra.
        """

        query = select(User).where(User.email == email).options(selectinload(User.roles).selectinload(UserRole.role))
        result = await self.db.execute(query)
        
        return result.scalar_one_or_none()

    async def get_user_by_rut(self, rut: str) -> User | None:
        """Obtiene un usuario por su RUT.

        Args:
            rut: Identificador RUT a buscar.

        Returns:
            La entidad `User` si existe; `None` si no se encuentra.
        """

        query = select(User).where(User.rut == rut)
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def get_user_by_enrollment(self, enrollment: str) -> User | None:
        """Obtiene un usuario por su matrícula institucional."""

        query = select(User).where(User.enrollment == enrollment)
        result = await self.db.execute(query)

        return result.scalar_one_or_none()
    
    async def get_user_by_id(self, user_id: int) -> User | None:
        """Obtiene un usuario por su identificador.

        La consulta incluye carga ansiosa de roles asociados (`User.roles`) y de
        la relación hacia `Role` a través de `UserRole`.

        Args:
            user_id: Identificador entero del usuario.

        Returns:
            La entidad `User` si existe; `None` si no se encuentra.
        """

        query = select(User).where(User.id == user_id).options(selectinload(User.roles).selectinload(UserRole.role))
        result = await self.db.execute(query)
        
        return result.scalar_one_or_none()
    
    async def create_user(self, user: User) -> User:
        """Persiste un usuario en la base de datos.

        Agrega la entidad a la sesión, confirma la transacción y refresca la
        instancia para asegurar que campos generados por la base de datos queden
        disponibles en el objeto.

        Args:
            user: Entidad `User` a crear.

        Returns:
            La misma entidad `User` persistida y refrescada.
        """

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

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
            Lista de entidades `User` que cumplen los filtros.
        """

        query = select(User).options(selectinload(User.roles).selectinload(UserRole.role))

        if is_active is not None:
            query = query.where(User.is_active == is_active)

        if email:
            query = query.where(User.email == email)

        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    User.first_name.ilike(pattern),
                    User.last_name.ilike(pattern),
                    User.email.ilike(pattern),
                    User.rut.ilike(pattern),
                    User.enrollment.ilike(pattern),
                )
            )

        if role_name:
            query = query.join(UserRole).join(Role).where(Role.name == role_name)

        sort_column = USER_SORT_COLUMNS.get(sort_by, User.created_at)
        if sort_dir == "asc":
            query = query.order_by(sort_column.asc(), User.id.asc())
        else:
            query = query.order_by(sort_column.desc(), User.id.desc())

        if limit is not None:
            query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def count_users(
        self,
        is_active: bool | None = None,
        email: str | None = None,
        search: str | None = None,
        role_name: str | None = None,
    ) -> int:
        """Cuenta usuarios con los mismos filtros del listado administrativo."""

        query = select(func.count(User.id))

        if is_active is not None:
            query = query.where(User.is_active == is_active)

        if email:
            query = query.where(User.email == email)

        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    User.first_name.ilike(pattern),
                    User.last_name.ilike(pattern),
                    User.email.ilike(pattern),
                    User.rut.ilike(pattern),
                    User.enrollment.ilike(pattern),
                )
            )

        if role_name:
            query = query.join(UserRole).join(Role).where(Role.name == role_name)

        result = await self.db.execute(query)

        return int(result.scalar_one())

    async def list_student_requirements_for_users(
        self,
        user_ids: list[int],
    ) -> list[StudentInternshipRequirement]:
        """Lista requisitos académicos para un conjunto de estudiantes."""

        if not user_ids:
            return []

        query = (
            select(StudentInternshipRequirement)
            .where(StudentInternshipRequirement.user_id.in_(user_ids))
            .order_by(
                StudentInternshipRequirement.user_id.asc(),
                StudentInternshipRequirement.id.asc(),
            )
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def list_student_internships_for_users(
        self,
        user_ids: list[int],
    ) -> list[Internship]:
        """Lista prácticas registradas para un conjunto de estudiantes."""

        if not user_ids:
            return []

        query = (
            select(Internship)
            .where(Internship.user_id.in_(user_ids))
            .options(selectinload(Internship.status))
            .order_by(
                Internship.user_id.asc(),
                Internship.internship_type.asc(),
                Internship.upload_date.desc(),
                Internship.id.desc(),
            )
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def count_active_users_with_role(
        self,
        role_name: str,
        exclude_user_id: int | None = None,
    ) -> int:
        """Cuenta usuarios activos que tienen un rol especifico."""

        query = (
            select(func.count(User.id))
            .join(UserRole)
            .join(Role)
            .where(User.is_active.is_(True), Role.name == role_name)
        )

        if exclude_user_id is not None:
            query = query.where(User.id != exclude_user_id)

        result = await self.db.execute(query)

        return int(result.scalar_one())

    async def update_user(self, user: User) -> User:
        """Actualiza un usuario existente en la base de datos.

        Args:
            user: Entidad `User` con cambios ya aplicados.

        Returns:
            La entidad `User` actualizada y refrescada.
        """

        await self.db.commit()
        await self.db.refresh(user)

        return user
