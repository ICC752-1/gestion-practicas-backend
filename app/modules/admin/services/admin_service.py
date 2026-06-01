"""Servicios de negocio del modulo admin.

Este modulo define `AdminService`, encargado de orquestar los casos de uso de
lectura administrativa y transformar entidades ORM a schemas HTTP propios.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.repositories.admin_repository import AdminRepository
from app.modules.admin.schemas.admin_schema import (
    AdminStudentInternshipRequirementItem,
    AdminUpdateStudentInternshipRequirementStatusRequest,
    AdminInternshipDetailResponse,
    AdminInternshipListItem,
    AdminInternshipStatusInfo,
    AdminInternshipStudentInfo,
    AdminStudentListItem,
    AdminSummaryByStatusItem,
    AdminSummaryResponse,
)
from app.modules.auth.models.user_model import User
from app.modules.internships.models.current_state_model import CurrentState
from app.modules.internships.models.internship_model import Internship



logger = logging.getLogger(__name__)

UNKNOWN_STATUS = "Sin estado"


class AdminService:
    """Orquesta casos de uso administrativos de solo lectura.

    Attributes:
        db         : Sesion asincrona utilizada durante el request.
        repository : Repositorio de acceso a datos administrativos.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el servicio con su sesion y repositorio.

        Args:
            db: Sesion asincrona de SQLAlchemy.
        """

        self.db = db
        self.repository = AdminRepository(db)

    async def get_summary(self) -> AdminSummaryResponse:
        """Obtiene el resumen administrativo del sistema.

        Returns:
            `AdminSummaryResponse` con totales globales y conteo por estado.
        """

        logger.info("Administrative summary requested")

        total_students = await self.repository.get_students_count()
        total_internships = await self.repository.get_internships_count()

        grouped_rows = await self.repository.get_internships_grouped_by_status()
        internships_by_status = self._build_summary_by_status_items(grouped_rows)

        summary = AdminSummaryResponse(
            total_students=total_students,
            total_internships=total_internships,
            internships_by_status=internships_by_status,
        )

        return summary

    async def get_students(self) -> list[AdminStudentListItem]:
        """Obtiene el listado administrativo de estudiantes.

        Returns:
            Lista de estudiantes en formato de respuesta del modulo `admin`.
        """

        logger.info("Administrative student list requested")

        students = await self.repository.get_students()

        student_items = self._build_student_list_items(students)

        return student_items

    async def get_internships(self) -> list[AdminInternshipListItem]:
        """Obtiene el listado administrativo de practicas.

        Returns:
            Lista de practicas en formato de respuesta del modulo `admin`.
        """

        logger.info("Administrative internships list requested")

        internships = await self.repository.get_internships()

        internship_items = self._build_internship_list_items(internships)

        return internship_items

    async def get_internship_detail(
        self,
        internship_id: int,
    ) -> AdminInternshipDetailResponse | None:
        """Obtiene el detalle administrativo de una practica.

        Args:
            internship_id  : Identificador entero de la practica.

        Returns:
            `AdminInternshipDetailResponse` si la practica existe; `None` en caso
            contrario.
        """

        logger.info(
            "Administrative internship detail requested",
            extra={"internship_id": internship_id},
        )

        internship = await self.repository.get_internship_by_id(internship_id)

        if internship is None:
            logger.warning(
                "Requested internship was not found",
                extra={"internship_id": internship_id},
            )
            return None

        student_info = self._build_student_info(internship.student)
        status_info = self._build_status_info(internship.status)

        detail = AdminInternshipDetailResponse(
            id=internship.id,
            org_name=internship.org_name,
            sector=internship.sector,
            address=internship.address,
            city=internship.city,
            org_phone=internship.org_phone,
            web=internship.web,
            start_date=internship.start_date,
            end_date=internship.end_date,
            schedule=internship.schedule,
            days=internship.days,
            modality=internship.modality,
            internship_address=internship.internship_address,
            act_description=internship.act_description,
            ben_description=internship.ben_description,
            amount=internship.amount,
            upload_date=internship.upload_date,
            status_id=internship.status_id,
            user_id=internship.user_id,
            student=student_info,
            status=status_info,
        )

        return detail

    async def get_student_internship_requirements(
        self,
        student_id: int,
    ) -> list[AdminStudentInternshipRequirementItem]:
        """Obtiene los requisitos de práctica asociados a un estudiante."""

        logger.info(
            "Administrative student internship requirements requested",
            extra={"student_id": student_id},
        )

        requirements = await self.repository.list_student_internship_requirements(
            student_id
        )

        return [
            AdminStudentInternshipRequirementItem(
                id=requirement.id,
                user_id=requirement.user_id,
                type=requirement.type,
                status=requirement.status,
                status_updated_at=requirement.status_updated_at,
                status_updated_by=requirement.status_updated_by,
                created_at=requirement.created_at,
                updated_at=requirement.updated_at,
            )
            for requirement in requirements
        ]

    async def update_student_internship_requirement_status(
        self,
        student_id: int,
        requirement_id: int,
        payload: AdminUpdateStudentInternshipRequirementStatusRequest,
        updated_by_user_id: int,
    ) -> AdminStudentInternshipRequirementItem | None:
        """Actualiza el estado de un requisito de práctica."""

        logger.info(
            "Updating student internship requirement status",
            extra={
                "student_id": student_id,
                "requirement_id": requirement_id,
                "status": payload.status,
                "updated_by": updated_by_user_id,
            },
        )

        requirement = await self.repository.get_student_internship_requirement(
            student_id,
            requirement_id,
        )
        if requirement is None:
            return None

        self._validate_requirement_status_transition(
            current_status=requirement.status,
            new_status=payload.status,
        )

        requirement.status = payload.status
        requirement.status_updated_at = datetime.now(timezone.utc)
        requirement.status_updated_by = updated_by_user_id

        updated_requirement = (
            await self.repository.update_student_internship_requirement(requirement)
        )

        return AdminStudentInternshipRequirementItem(
            id=updated_requirement.id,
            user_id=updated_requirement.user_id,
            type=updated_requirement.type,
            status=updated_requirement.status,
            status_updated_at=updated_requirement.status_updated_at,
            status_updated_by=updated_requirement.status_updated_by,
            created_at=updated_requirement.created_at,
            updated_at=updated_requirement.updated_at,
        )

    def _build_student_info(
        self,
        student: User | None,
    ) -> AdminInternshipStudentInfo | None:
        """Construye el bloque de estudiante asociado a una practica."""

        if student is None:
            return None

        student_info = AdminInternshipStudentInfo(
            id=student.id,
            email=student.email,
            first_name=student.first_name,
            last_name=student.last_name,
            rut=student.rut,
        )

        return student_info

    def _build_student_list_items(
        self,
        students: list[User],
    ) -> list[AdminStudentListItem]:
        """Construye el listado administrativo de estudiantes."""

        student_items: list[AdminStudentListItem] = []

        for student in students:
            student_item = AdminStudentListItem(
                id=student.id,
                email=student.email,
                first_name=student.first_name,
                last_name=student.last_name,
                rut=student.rut,
                is_active=student.is_active,
            )
            student_items.append(student_item)

        return student_items

    def _build_summary_by_status_items(
        self,
        grouped_rows: list[tuple[str | None, int]],
    ) -> list[AdminSummaryByStatusItem]:
        """Construye el desglose de practicas por estado para el resumen."""

        internships_by_status: list[AdminSummaryByStatusItem] = []

        for status_title, total in grouped_rows:
            status_name = status_title
            if status_name is None:
                status_name = UNKNOWN_STATUS

            summary_item = AdminSummaryByStatusItem(
                status=status_name,
                total=total,
            )
            internships_by_status.append(summary_item)

        return internships_by_status

    def _build_internship_list_items(
        self,
        internships: list[Internship],
    ) -> list[AdminInternshipListItem]:
        """Construye el listado administrativo de practicas."""

        internship_items: list[AdminInternshipListItem] = []

        for internship in internships:
            student_info = self._build_student_info(internship.student)
            status_info = self._build_status_info(internship.status)

            internship_item = AdminInternshipListItem(
                id=internship.id,
                org_name=internship.org_name,
                city=internship.city,
                start_date=internship.start_date,
                end_date=internship.end_date,
                upload_date=internship.upload_date,
                user_id=internship.user_id,
                student=student_info,
                status=status_info,
            )
            internship_items.append(internship_item)

        return internship_items

    def _build_status_info(
        self,
        status: CurrentState | None,
    ) -> AdminInternshipStatusInfo | None:
        """Construye el bloque de estado asociado a una practica."""

        if status is None:
            return None

        status_info = AdminInternshipStatusInfo(
            id=status.id,
            title=status.title,
            description=status.description,
        )

        return status_info

    def _validate_requirement_status_transition(
        self,
        current_status: str,
        new_status: str,
    ) -> None:
        """Valida transiciones de estado para requisitos de práctica."""

        if current_status == new_status:
            return

        allowed_transitions: dict[str, set[str]] = {
            "Pendiente": {"Habilitada"},
            "Habilitada": {"En revisión"},
            "En revisión": {"Aprobada", "Rechazada"},
            "Rechazada": {"Habilitada"},
            "Aprobada": set(),
        }

        if new_status not in allowed_transitions.get(current_status, set()):
            raise ValueError(
                f"Invalid status transition from {current_status} to {new_status}"
            )
