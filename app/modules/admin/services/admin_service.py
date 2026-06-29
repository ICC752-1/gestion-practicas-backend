"""Servicios de negocio del modulo admin.

Este modulo define `AdminService`, encargado de orquestar consultas
administrativas y la gestion de requisitos del estudiante.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.repositories.admin_repository import AdminRepository
from app.modules.admin.schemas.admin_schema import (
    AdminInternshipDetailResponse,
    AdminInternshipListItem,
    AdminInternshipStatusFilter,
    AdminInternshipStatusInfo,
    AdminInternshipStudentInfo,
    AdminRegistrationRequirementItem,
    AdminStudentInternshipRequirementItem,
    AdminStudentListItem,
    AdminSummaryByStatusItem,
    AdminSummaryResponse,
    AdminUpdateInternshipSchoolInsuranceRequest,
    AdminUpdateSchoolInsuranceRequest,
    AdminUpdateStudentInternshipRequirementStatusRequest,
)
from app.modules.auth.models.user_model import User
from app.modules.internships.models.current_state_model import CurrentState
from app.modules.internships.models.internship_model import (
    Internship,
    SchoolInsuranceStatusEnum,
)
from app.modules.internships.models.student_internship_requirement_model import (
    RegistrationRequirementType,
    StudentRegistrationRequirement,
)
from app.modules.notifications.services.notification_service import (
    NotificationService,
)
from app.modules.notifications.utils.notification_event_helpers import (
    build_requirement_status_changed_notification,
)



logger = logging.getLogger(__name__)

UNKNOWN_STATUS = "Sin estado"
CANCELLED_STATUS_TITLE = "Anulada"
PENDING_STATUS_TITLE = "Pendiente"
IN_REVIEW_STATUS_TITLE = "En revisión"
IN_REVIEW_DIRAE_STATUS_TITLE = "En revisión DIRAE"
APPROVED_STATUS_TITLE = "Aprobada"
REJECTED_STATUS_TITLE = "Rechazada"
LEGACY_REJECTED_STATUS_TITLE = "Reprobada"


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


STATUS_LABEL_TO_ADMIN_FILTER: dict[str, AdminInternshipStatusFilter] = {
    PENDING_STATUS_TITLE: "submitted",
    IN_REVIEW_STATUS_TITLE: "in_review",
    IN_REVIEW_DIRAE_STATUS_TITLE: "in_review",
    APPROVED_STATUS_TITLE: "approved",
    REJECTED_STATUS_TITLE: "rejected",
    LEGACY_REJECTED_STATUS_TITLE: "rejected",
}


class AdminService:
    """Orquesta casos de uso administrativos.

    Attributes:
        db : Sesion asincrona utilizada durante el request.
        repository : Repositorio de acceso a datos administrativos.
        notification_service : Servicio de notificaciones para despachar
            eventos de cambio de estado de requisitos (opcional).
    """

    def __init__(
        self,
        db: AsyncSession,
        notification_service: NotificationService | None = None,
    ) -> None:
        """Inicializa el servicio con su sesion y repositorio.

        Args:
            db: Sesion asincrona de SQLAlchemy.
            notification_service: Servicio de notificaciones para despachar
                eventos tras cambios de estado de requisitos. Si es `None`,
                no se generan notificaciones.
        """

        self.db = db
        self.repository = AdminRepository(db)
        self.notification_service = notification_service

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

    async def get_internships(
        self,
        status_filter: AdminInternshipStatusFilter | None = None,
    ) -> list[AdminInternshipListItem]:
        """Obtiene el listado administrativo de practicas.

        Args:
            status_filter: Estado normalizado opcional para dashboard.

        Returns:
            Lista de practicas en formato de respuesta del modulo `admin`.
        """

        logger.info(
            "Administrative internships list requested",
            extra={"status_filter": status_filter},
        )

        internships = await self.repository.get_internships()

        if status_filter is not None:
            internships = [
                internship
                for internship in internships
                if self._matches_status_filter(internship, status_filter)
            ]

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

        return self._build_internship_detail(internship)

    async def update_internship_school_insurance(
        self,
        internship_id: int,
        payload: AdminUpdateInternshipSchoolInsuranceRequest,
        updated_by_user_id: int,
    ) -> AdminInternshipDetailResponse | None:
        """Actualiza la validacion de seguro escolar de una solicitud."""

        internship = await self.repository.get_internship_by_id(internship_id)
        if internship is None:
            return None

        if internship.is_cancelled:
            raise ValueError(
                "No se puede actualizar el seguro escolar de una solicitud anulada."
            )

        status = SchoolInsuranceStatusEnum(payload.status)
        updated = await self.repository.update_internship_school_insurance(
            internship=internship,
            status=status,
            updated_by_user_id=updated_by_user_id,
            notes=payload.notes,
        )

        return self._build_internship_detail(updated)

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

        previous_status = requirement.status
        requirement.status = payload.status
        requirement.status_updated_at = _utc_now_naive()
        requirement.status_updated_by = updated_by_user_id

        updated_requirement = (
            await self.repository.update_student_internship_requirement(requirement)
        )
        student = await self.repository.get_user_by_id(updated_requirement.user_id)

        await self._dispatch_requirement_notification(
            recipient_user_id=updated_requirement.user_id,
            recipient_email=student.email if student is not None else None,
            requirement_id=updated_requirement.id,
            requirement_type=updated_requirement.type,
            new_status=updated_requirement.status,
            previous_status=previous_status,
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

    async def get_student_registration_requirements(
        self,
        student_id: int,
    ) -> list[AdminRegistrationRequirementItem] | None:
        """Obtiene los prerrequisitos institucionales de un estudiante."""

        student = await self.repository.get_user_by_id(student_id)
        if student is None or not self._is_student(student):
            return None

        requirements = await self.repository.list_student_registration_requirements(
            student_id
        )

        return [
            AdminRegistrationRequirementItem.model_validate(requirement)
            for requirement in requirements
        ]

    async def update_school_insurance_requirement(
        self,
        student_id: int,
        payload: AdminUpdateSchoolInsuranceRequest,
        updated_by_user_id: int,
    ) -> AdminRegistrationRequirementItem | None:
        """Registra o actualiza el cumplimiento institucional del seguro escolar."""

        student = await self.repository.get_user_by_id(student_id)
        if student is None or not self._is_student(student):
            return None

        requirement = (
            await self.repository.get_student_registration_requirement(
                student_id=student_id,
                requirement=RegistrationRequirementType.SCHOOL_INSURANCE.value,
            )
        )
        previous_status = None if requirement is None else requirement.is_completed

        if requirement is None:
            requirement = StudentRegistrationRequirement(
                user_id=student_id,
                requirement=RegistrationRequirementType.SCHOOL_INSURANCE,
            )

        requirement.is_completed = payload.is_completed
        requirement.completed_at = (
            _utc_now_naive() if payload.is_completed else None
        )
        requirement.updated_by = updated_by_user_id

        updated_requirement = (
            await self.repository.save_student_registration_requirement(requirement)
        )

        await self._dispatch_requirement_notification(
            recipient_user_id=student_id,
            recipient_email=student.email,
            requirement_id=updated_requirement.id,
            requirement_type=RegistrationRequirementType.SCHOOL_INSURANCE.value,
            new_status="Completado" if payload.is_completed else "Pendiente",
            previous_status=(
                None
                if previous_status is None
                else ("Completado" if previous_status else "Pendiente")
            ),
        )

        return AdminRegistrationRequirementItem.model_validate(updated_requirement)

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
            degree=getattr(student, "degree", None),
            cod_degree=getattr(student, "cod_degree", None),
        )

        return student_info

    def _is_student(self, user: User) -> bool:
        """Indica si el usuario posee el rol de estudiante."""

        return any(
            user_role.role.name == "Estudiante"
            for user_role in user.roles
            if user_role.role is not None
        )

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
                degree=getattr(student, "degree", None),
                cod_degree=getattr(student, "cod_degree", None),
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
                internship_type=internship.internship_type,
                student=student_info,
                status=status_info,
                is_cancelled=internship.is_cancelled,
                insurance_status=getattr(
                    internship,
                    "insurance_status",
                    SchoolInsuranceStatusEnum.pending,
                ),
            )
            internship_items.append(internship_item)

        return internship_items

    def _build_internship_detail(
        self,
        internship: Internship,
    ) -> AdminInternshipDetailResponse:
        """Construye el contrato completo del detalle administrativo."""

        return AdminInternshipDetailResponse(
            id=internship.id,
            org_name=internship.org_name,
            sector=internship.sector,
            address=internship.address,
            city=internship.city,
            org_phone=internship.org_phone,
            web=internship.web,
            supervisor_name=internship.supervisor_name,
            supervisor_profession=internship.supervisor_profession,
            supervisor_position=internship.supervisor_position,
            supervisor_department=internship.supervisor_department,
            supervisor_email=internship.supervisor_email,
            supervisor_phone=internship.supervisor_phone,
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
            internship_period=internship.internship_period,
            internship_type=internship.internship_type,
            has_school_insurance=internship.has_school_insurance,
            student=self._build_student_info(internship.student),
            status=self._build_status_info(internship.status),
            is_cancelled=internship.is_cancelled,
            cancelled_at=internship.cancelled_at,
            cancellation_reason=internship.cancellation_reason,
            insurance_status=getattr(
                internship,
                "insurance_status",
                SchoolInsuranceStatusEnum.pending,
            ),
            insurance_validated_by=getattr(
                internship,
                "insurance_validated_by",
                None,
            ),
            insurance_validated_at=getattr(
                internship,
                "insurance_validated_at",
                None,
            ),
            insurance_notes=getattr(internship, "insurance_notes", None),
        )

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

    def _matches_status_filter(
        self,
        internship: Internship,
        status_filter: AdminInternshipStatusFilter,
    ) -> bool:
        """Evalua si una practica corresponde al filtro normalizado admin."""

        if internship.is_cancelled:
            return False

        status_title = PENDING_STATUS_TITLE
        if internship.status is not None and internship.status.title:
            status_title = internship.status.title

        return STATUS_LABEL_TO_ADMIN_FILTER.get(status_title) == status_filter

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

    async def _dispatch_requirement_notification(
        self,
        recipient_user_id: int,
        recipient_email: str | None,
        requirement_id: int,
        requirement_type: str,
        new_status: str,
        previous_status: str | None = None,
    ) -> None:
        """Despacha una notificacion de cambio de estado de requisito.

        Si el servicio de notificaciones no esta configurado, la operacion se
        ignora silenciosamente. Los errores de notificacion no interrumpen el
        flujo principal de negocio.

        Args:
            recipient_user_id: Identificador del usuario destinatario.
            recipient_email: Correo del usuario destinatario, si existe.
            requirement_id: Identificador del requisito actualizado.
            requirement_type: Tipo/nombre del requisito.
            new_status: Nuevo estado asignado al requisito.
            previous_status: Estado anterior del requisito.
        """

        if self.notification_service is None:
            return

        notification = build_requirement_status_changed_notification(
            recipient_user_id=recipient_user_id,
            recipient_email=recipient_email,
            requirement_id=requirement_id,
            requirement_type=requirement_type,
            new_status=new_status,
            previous_status=previous_status,
        )

        try:
            await self.notification_service.create_and_dispatch(notification)
        except Exception:
            logger.warning(
                "Fallo al despachar notificacion de requisito (id=%s). "
                "El flujo de negocio continua normalmente.",
                requirement_id,
                exc_info=True,
            )
