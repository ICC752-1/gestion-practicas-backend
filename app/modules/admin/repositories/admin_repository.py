"""Repositorio de acceso a datos del modulo admin.

Este modulo define `AdminRepository`, encargado de encapsular consultas de
lectura administrativas sobre estudiantes y practicas.
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models.role_model import Role
from app.modules.auth.models.user_model import User
from app.modules.auth.models.user_role_model import UserRole
from app.modules.internships.models.current_state_model import CurrentState
from app.modules.internships.models.internship_model import Internship
from app.modules.internships.models.student_internship_requirement_model import (
    StudentInternshipRequirement,
)


logger = logging.getLogger(__name__)

STUDENT_ROLE = "Estudiante"


class AdminRepository:
    """Implementa consultas administrativas sobre usuarios y practicas.

    Attributes:
        db: Sesion asincrona (`AsyncSession`) utilizada para ejecutar consultas.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el repositorio con una sesion de base de datos.

        Args:
            db: Sesion asincrona de SQLAlchemy.
        """

        self.db = db

    async def get_students_count(self) -> int:
        """Cuenta usuarios que poseen rol `Estudiante`.

        Returns:
            Cantidad total de usuarios asociados al rol `Estudiante`.
        """

        logger.debug("Counting students with role Estudiante")

        query = (
            select(func.count(User.id))
            .select_from(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.name == STUDENT_ROLE)
        )
        result = await self.db.execute(query)

        return result.scalar_one()

    async def get_internships_count(self) -> int:
        """Cuenta el total de practicas registradas.

        Returns:
            Cantidad total de registros en `Internship`.
        """

        logger.debug("Counting internships")

        query = select(func.count(Internship.id))
        result = await self.db.execute(query)

        return result.scalar_one()

    async def get_internships_grouped_by_status(self) -> list[tuple[str | None, int]]:
        """Agrupa practicas por nombre del estado actual.

        Returns:
            Lista de tuplas `(status_title, total)` para cada grupo encontrado.
            Si una practica no posee estado asignado, el titulo puede ser `None`.
        """

        logger.debug("Counting internships grouped by status")

        query = (
            select(CurrentState.title, func.count(Internship.id))
            .select_from(Internship)
            .outerjoin(CurrentState, CurrentState.id == Internship.status_id)
            .group_by(CurrentState.title)
            .order_by(CurrentState.title.asc())
        )
        result = await self.db.execute(query)
        rows = result.all()

        grouped_internships: list[tuple[str | None, int]] = []
        for title, total in rows:
            grouped_internships.append((title, total))

        return grouped_internships

    async def get_students(self) -> list[User]:
        """Obtiene usuarios asociados al rol `Estudiante`.

        Returns:
            Lista de estudiantes ordenada por apellido, nombre e identificador.
        """

        logger.debug("Fetching administrative student list")

        query = (
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.name == STUDENT_ROLE)
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .order_by(User.last_name.asc(), User.first_name.asc(), User.id.asc())
        )
        result = await self.db.execute(query)
        students = result.scalars().unique().all()

        return list(students)

    async def get_internships(self) -> list[Internship]:
        """Obtiene el listado administrativo de practicas.

        Returns:
            Lista de practicas con estudiante y estado actual cargados.
        """

        logger.debug("Fetching administrative internships list")

        query = (
            select(Internship)
            .options(
                selectinload(Internship.student),
                selectinload(Internship.status),
            )
            .order_by(Internship.upload_date.desc(), Internship.id.desc())
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def get_internship_by_id(self, internship_id: int) -> Internship | None:
        """Obtiene el detalle administrativo de una practica por identificador.

        Args:
            internship_id: Identificador entero de la practica.

        Returns:
            La entidad `Internship` si existe; `None` en caso contrario.
        """

        logger.debug(
            "Fetching administrative internship detail",
            extra={"internship_id": internship_id},
        )

        query = (
            select(Internship)
            .where(Internship.id == internship_id)
            .options(
                selectinload(Internship.student),
                selectinload(Internship.status),
            )
        )
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def list_student_internship_requirements(
        self,
        student_id: int,
    ) -> list[StudentInternshipRequirement]:
        """Obtiene los requisitos de prácticas asociados a un estudiante."""

        logger.debug(
            "Fetching student internship requirements",
            extra={"student_id": student_id},
        )

        query = (
            select(StudentInternshipRequirement)
            .where(StudentInternshipRequirement.user_id == student_id)
            .order_by(StudentInternshipRequirement.id.asc())
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def get_student_internship_requirement(
        self,
        student_id: int,
        requirement_id: int,
    ) -> StudentInternshipRequirement | None:
        """Obtiene un requisito de práctica por estudiante y id."""

        logger.debug(
            "Fetching student internship requirement",
            extra={"student_id": student_id, "requirement_id": requirement_id},
        )

        query = (
            select(StudentInternshipRequirement)
            .where(StudentInternshipRequirement.user_id == student_id)
            .where(StudentInternshipRequirement.id == requirement_id)
        )
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def update_student_internship_requirement(
        self,
        requirement: StudentInternshipRequirement,
    ) -> StudentInternshipRequirement:
        """Persiste cambios en un requisito de práctica."""

        self.db.add(requirement)
        await self.db.commit()
        await self.db.refresh(requirement)

        return requirement
