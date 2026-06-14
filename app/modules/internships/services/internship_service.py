"""Servicios de negocio para practicas.

Este modulo define `InternshipService`, encargado de coordinar los casos de uso
del modulo `internships` y delegar operaciones de persistencia al repositorio.
"""
import logging

from datetime import UTC, datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from typing import Any

from app.core.config import config
from app.modules.internships.models.current_state_model import CurrentState
from app.modules.internships.models.induction_model import InductionAttempt
from app.modules.internships.models.internship_model import (
    Internship,
    PracticePeriodEnum,
    PracticeTypeEnum,
)
from app.modules.internships.models.internship_status_history_model import (
    InternshipStatusHistory,
)
from app.modules.internships.repositories.internship_repository import (
    InternshipRepository,
)
from app.modules.internships.schemas.internship_schema import (
    DashboardInternshipStatus,
    InductionAttemptRequest,
    InductionAttemptResponse,
    InductionContentVersionResponse,
    InternshipCreateRequest,
    InternshipAdminUpdateRequest,
    InternshipDashboardListItem,
    InternshipDashboardStatsResponse,
    InternshipDashboardStudentResponse,
    RegistrationEligibilityResponse,
    DuplicateInternshipTypeDetail,
    StudentInternshipActionAvailabilityResponse,
    StudentInternshipUpdateRequest,
)
from app.modules.auth.models.user_model import User
from app.modules.internships.models.internship_exception_model import InternshipException

from app.modules.notifications.services.notification_service import (
    NotificationService,
)
from app.modules.notifications.utils.notification_event_helpers import (
    build_internship_approved_notification,
    build_internship_created_notification,
    build_internship_derived_notification,
    build_internship_rejected_notification,
)

logger = logging.getLogger(__name__)

DEFAULT_DASHBOARD_STATUS_LABEL = "Pendiente"
PENDING_STATUS_TITLE = "Pendiente"
IN_REVIEW_STATUS_TITLE = "En revisión"
APPROVED_STATUS_TITLE = "Aprobada"
REJECTED_STATUS_TITLE = "Rechazada"
LEGACY_REJECTED_STATUS_TITLE = "Reprobada"
IN_REVIEW_DIRAE_STATUS_TITLE = "En revisión DIRAE"
TERMINAL_STATES = {
    APPROVED_STATUS_TITLE, 
    REJECTED_STATUS_TITLE, 
    LEGACY_REJECTED_STATUS_TITLE, }

SEASONAL_PERIODS = {"Verano", "Invierno"}

INITIAL_HISTORY_REASON = "Creación inicial de solicitud de práctica"
STATUS_LABEL_TO_DASHBOARD_STATUS: dict[str, DashboardInternshipStatus] = {
    PENDING_STATUS_TITLE: "submitted",
    IN_REVIEW_STATUS_TITLE: "in_review",
    APPROVED_STATUS_TITLE: "approved",
    REJECTED_STATUS_TITLE: "rejected",
    LEGACY_REJECTED_STATUS_TITLE: "rejected",
}
STATUS_TITLE_ALIASES = {
    LEGACY_REJECTED_STATUS_TITLE: REJECTED_STATUS_TITLE,
}

ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    PENDING_STATUS_TITLE: {
        IN_REVIEW_STATUS_TITLE,
        IN_REVIEW_DIRAE_STATUS_TITLE,
        APPROVED_STATUS_TITLE,
        REJECTED_STATUS_TITLE,
    },
    IN_REVIEW_STATUS_TITLE: {
        APPROVED_STATUS_TITLE,
        REJECTED_STATUS_TITLE,
        IN_REVIEW_DIRAE_STATUS_TITLE
    },
    IN_REVIEW_DIRAE_STATUS_TITLE: {     
        APPROVED_STATUS_TITLE,
        REJECTED_STATUS_TITLE,
    },

    APPROVED_STATUS_TITLE: set(),
    REJECTED_STATUS_TITLE: set(),
}

EMPTY_DASHBOARD_STATS = {
    "submitted": 0,
    "in_review": 0,
    "approved": 0,
    "rejected": 0,
}

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "Encargado de practica": [
        "approve",
        "reject",
        "grant_exception",
        "admin_edit",
        "cancel",
    ],
    "Director de carrera": [
        "approve",
        "reject",
        "grant_exception",
        "admin_edit",
        "cancel",
    ],
    "Secretaria de Carrera": ["derive"]
}

EXCEPTABLE_RULES = {"school_insurance", "sequentiality", "sequentiality_thesis", "parallel_course"}
APPROVED_STATUS_TITLE_SET = {APPROVED_STATUS_TITLE}

INTERNSHIP_CREATION_NOTIFICATION_ROLES = {
    "Encargado de practica",
    "Director de carrera",
}
STUDENT_ALLOWED_HISTORY_ACTIONS = {
    None,
    "student_update",
}
STUDENT_BLOCKING_HISTORY_ACTIONS = {
    "admin_update",
    "approve",
    "reject",
    "derive",
    "cancel",
    "student_cancel",
}


class InternshipService:
    """Orquesta casos de uso relacionados con practicas.

    Attributes:
        internship_repository: Repositorio de acceso a datos para practicas.
        notification_service: Servicio de notificaciones para despachar
            eventos administrativos (opcional).
    """

    def __init__(
        self,
        internship_repository: InternshipRepository,
        notification_service: NotificationService | None = None,
        student_edit_window_hours: int | None = None,
    ) -> None:
        """Inicializa el servicio con sus dependencias.

        Args:
            internship_repository: Repositorio para consultar y persistir
                practicas.
            notification_service: Servicio de notificaciones para despachar
                eventos tras acciones administrativas. Si es `None`, no se
                generan notificaciones.
            student_edit_window_hours: Ventana temporal para correcciones y
                anulaciones recientes del propietario. Si es `None`, se usa la
                configuracion de aplicacion.
        """

        self.internship_repository = internship_repository
        self.notification_service = notification_service
        self.student_edit_window_hours = (
            student_edit_window_hours
            if student_edit_window_hours is not None
            else config.STUDENT_EFFECTIVE_CORRECTION_WINDOW_HOURS
        )

    async def create_internship(
        self,
        internship_data: InternshipCreateRequest,
        user_id: int,
    ) -> Internship:
        """Crea una practica asociada a un usuario.

        El campo ``has_school_insurance`` se computa internamente a partir
        de los registros de prerrequisitos del estudiante, no desde el
        frontend. Si el estudiante tiene registrado el cumplimiento del
        seguro escolar en ``StudentRegistrationRequirement``, se asigna
        como ``True``; en caso contrario, ``False``.

        Args:
            internship_data: Datos validados para crear la practica.
            user_id: Identificador entero del usuario propietario.

        Returns:
            Entidad `Internship` persistida.
        """

        initial_status = await self._get_required_state(PENDING_STATUS_TITLE)
        data = internship_data.model_dump()
        insurance_req = await self.internship_repository.get_student_requirement(
            user_id=user_id,
            requirement="school_insurance",
        )
        data["has_school_insurance"] = insurance_req.is_completed if insurance_req else False

        blocking_internship = (
            await self.internship_repository.get_blocking_internship_for_registration(
                user_id=user_id,
                internship_type=internship_data.internship_type,
            )
        )
        if blocking_internship is not None:
            self._raise_duplicate_internship_type(blocking_internship)

        internship = Internship(
            **data,
            user_id=user_id,
            status_id=initial_status.id,
            blocks_new_registration=True,
        )

        try:
            created_internship = (
                await self.internship_repository.create_internship_with_history(
                    internship=internship,
                    initial_status=initial_status,
                    actor_id=user_id,
                    reason=INITIAL_HISTORY_REASON,
                    metadata={"event": "internship_created"},
                )
            )
        except IntegrityError:
            await self.internship_repository.rollback()
            blocking_internship = (
                await self.internship_repository.get_blocking_internship_for_registration(
                    user_id=user_id,
                    internship_type=internship_data.internship_type,
                )
            )
            if blocking_internship is not None:
                self._raise_duplicate_internship_type(blocking_internship)
            raise

        await self._dispatch_internship_created_notifications(created_internship)

        return created_internship

    async def get_internship(self, internship_id: int) -> Internship | None:
        """Obtiene una practica por identificador.

        Args:
            internship_id: Identificador entero de la practica.

        Returns:
            La entidad `Internship` si existe; `None` si no se encuentra.
        """

        return await self.internship_repository.get_internship_by_id(internship_id)

    async def list_user_internships(self, user_id: int) -> list[Internship]:
        """Lista las practicas asociadas a un usuario.

        Args:
            user_id: Identificador entero del usuario propietario.

        Returns:
            Lista de entidades `Internship` asociadas al usuario.
        """

        return await self.internship_repository.list_internships_by_user(user_id)

    async def list_internship_tracking(
        self,
        internship_id: int,
    ) -> list[InternshipStatusHistory]:
        """Lista el historial de estados de una practica.

        Args:
            internship_id: Identificador entero de la practica.

        Returns:
            Entradas de historial ordenadas cronologicamente.
        """

        return await self.internship_repository.list_internship_status_history(
            internship_id=internship_id,
        )

    async def transition_internship_status(
        self,
        internship_id: int,
        new_status_title: str,
        actor_id: int,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Internship | None:
        """Cambia el estado de una practica y registra su historial.

        Este metodo no se expone por HTTP en 9.3. Queda disponible como caso de
        uso interno para que las acciones administrativas de 9.5 reutilicen la
        misma matriz de transiciones.

        Args:
            internship_id: Identificador de la practica a actualizar.
            new_status_title: Estado destino solicitado.
            actor_id: Usuario que ejecuta la transicion.
            reason: Motivo funcional de la transicion.
            metadata: Datos auxiliares de contexto, si existen.

        Returns:
            Practica actualizada o `None` si no existe.

        Raises:
            ValueError: Si el estado destino no existe o la transicion no esta
                permitida.
        """

        internship = await self.internship_repository.get_internship_by_id(
            internship_id,
        )
        if internship is None:
            return None

        previous_status = internship.status
        current_status_title = self._status_title_or_default(previous_status)
        canonical_new_status_title = self._canonical_status_title(new_status_title)

        self._validate_status_transition(
            current_status_title=current_status_title,
            new_status_title=canonical_new_status_title,
        )

        new_status = await self._get_required_state(canonical_new_status_title)

        return await self.internship_repository.update_internship_status_with_history(
            internship=internship,
            previous_status=previous_status,
            new_status=new_status,
            actor_id=actor_id,
            reason=reason,
            metadata=metadata,
        )

    async def list_dashboard_internships(
        self,
        status_filter: DashboardInternshipStatus | None = None,
    ) -> list[InternshipDashboardListItem]:
        """Lista practicas para el dashboard de coordinador/director.

        Args:
            status_filter: Estado normalizado opcional para filtrar resultados.

        Returns:
            Lista de practicas resumidas con estudiante y estado normalizado.
        """

        internships = await self.internship_repository.list_dashboard_internships()
        items = [
            self._build_dashboard_item(internship)
            for internship in internships
        ]

        if status_filter is None:
            return items

        return [
            item
            for item in items
            if item.status == status_filter
        ]

    async def get_dashboard_stats(self) -> InternshipDashboardStatsResponse:
        """Obtiene conteos agregados para el dashboard de coordinador/director.
        
        Returns:
            Totales globales y por estado normalizado
        """

        internships = await self.internship_repository.list_dashboard_internships()
        counters = dict(EMPTY_DASHBOARD_STATS)

        for internship in internships:
            normalized_status, _ = self._normalize_dashboard_status(internship)
            counters[normalized_status] += 1

        return InternshipDashboardStatsResponse(
            total=len(internships),
            submitted=counters["submitted"],
            in_review=counters["in_review"],
            approved=counters["approved"],
            rejected=counters["rejected"],
        )

    def _build_dashboard_item(
        self,
        internship: Internship,

    ) -> InternshipDashboardListItem:
        normalized_status, status_label = self._normalize_dashboard_status(internship)
        student = None

        if internship.student is not None:
            student = InternshipDashboardStudentResponse.model_validate(
                internship.student,
            )

        return InternshipDashboardListItem(
            id=internship.id,
            org_name=internship.org_name,
            city=internship.city,
            internship_type=internship.internship_type,
            start_date=internship.start_date,
            end_date=internship.end_date,
            upload_date=internship.upload_date,
            status=normalized_status,
            status_label=status_label,
            student=student,
        )

    def _normalize_dashboard_status(
        self,
        internship: Internship,
    ) -> tuple[DashboardInternshipStatus, str]:
        status_label = DEFAULT_DASHBOARD_STATUS_LABEL

        if internship.status is not None and internship.status.title:
            status_label = internship.status.title

        normalized_status = STATUS_LABEL_TO_DASHBOARD_STATUS.get(
            status_label,
            "submitted",
        )

        return normalized_status, status_label

    async def _get_required_state(self, title: str) -> CurrentState:
        """Obtiene un estado existente o falla si falta la semilla base."""

        state = await self.internship_repository.get_state_by_title(title)
        if state is None:
            raise ValueError(f"Required internship status not found: {title}")

        return state

    def _status_title_or_default(self, status: CurrentState | None) -> str:
        """Normaliza un estado actual ausente como `Pendiente`."""

        if status is None or not status.title:
            return PENDING_STATUS_TITLE

        return self._canonical_status_title(status.title)

    def _canonical_status_title(self, status_title: str) -> str:
        """Convierte nombres historicos a su estado canonico."""

        return STATUS_TITLE_ALIASES.get(status_title, status_title)

    def _validate_status_transition(
        self,
        current_status_title: str,
        new_status_title: str,
    ) -> None:
        """Valida una transicion funcional de estado de practica."""

        if current_status_title == new_status_title:
            raise ValueError(
                f"Invalid status transition from {current_status_title} "
                f"to {new_status_title}"
            )

        allowed_destinations = ALLOWED_STATUS_TRANSITIONS.get(
            current_status_title,
            set(),
        )
        if new_status_title not in allowed_destinations:
            raise ValueError(
                f"Invalid status transition from {current_status_title} "
                f"to {new_status_title}"
            )

    def _get_user_actions(self, user: User) -> set[str]:
        """
        Obtiene el conjunto de acciones permitidas para un usuario según sus roles.

        Itera sobre todos los roles asignados al usuario y consolida los permisos
        configurados en `ROLE_PERMISSION`.

        Args:
            user: Entidad del usuario autenticado que conntiene sus roles.

        Returns:
            Un conjunto con los identificadores de las acciones permitidas.

        """

        allowed = set()
        for user_role in user.roles:
            role_name = user_role.role.name
            allowed.update(ROLE_PERMISSIONS.get(role_name, []))
        return allowed
    
    def _require_action(self, user: User, action: str) -> None:
        """
        Valida si el usuario tiene permisos para ejecutar una acción específica.

        Args:
            user: Entidad del usuario que intenta realizar la acción.
            action:  Nombre de la acción requerida (ej, 'approve', 'reject').

        Raises:
            HTTPException: Con código de estado 403 si el usuario no cuenta 
            con la acción permitidad en sus roles.
        """
        if action not in self._get_user_actions(user):
            logger.warning("Usuario ID: %s intentó realizar acción '%s' sin permisos suficientes", user.id, action)
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
    def _require_comment(self, comment: str | None, action: str) -> None:
        """
        Verifica la obligatoriedad de un comentario/motivo para ciertas acciones.

        Para acciones de rechazo o derivación, se exige que el comentario no esté
        vacío ni contenga únicamente espacios en blanco.

        Args:
            comment: Texto del motivo o comentario ingresado por el actor.
            action: Tipo de acción que se está evaluando ('reject' o 'derive').

        Raises:
            HTTPException: Con código de estado 400 si la acción exige un comentario
                y este no fue provisto.
        """

        if action in ("reject", "derive") and (not comment or not comment.strip()):
            logger.warning("Intento de ejecutar '%s' sin proporcionar el comentario obligatorio requerido", action)
            raise HTTPException(
                status_code=400, 
                detail=f"El motivo/comentario es obligatorio para la acción: {action}"
            )

    async def _do_transition(
        self,
        internship: Internship,
        new_status_title: str,
        actor_id: int,
        reason: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> Internship:
        
        """Ejecuta de manera interna la transición de estado de una práctica y registra su historial.

        Args:
            internship: Entidad de la práctica que cambiará de estado.
            new_status_title: Título del nuevo estado destino.
            actor_id: Identificador del usuario que realiza la operación.
            reason: Comentario o justificación del cambio de estado.
            metadata: Datos contextuales adicionales para el registro del historial.

        Returns:
            La entidad `Internship` actualizada tras aplicar el cambio en el repositorio.
        """

        new_status = await self._get_required_state(new_status_title)
        return await self.internship_repository.update_internship_status_with_history(
            internship=internship,
            previous_status=internship.status,
            new_status=new_status,
            actor_id=actor_id,
            reason=reason,
            metadata=metadata,
        )    

    async def approve(
        self,
        internship_id: int,
        actor: User,
        comment: str | None,
        skip_review: bool = False,
    ) -> Internship:
        """Aprueba una practica adaptando el estado destino segun la matriz de negocio.

        El flujo no es secuencial obligatorio. Encargado de practica y Director
        de carrera tienen los mismos permisos. El estado destino se determina
        combinando el estado actual y el flag ``skip_review``:

        - ``Pendiente`` → ``En revisión`` (flujo regular).
        - ``Pendiente`` → ``Aprobada`` (``skip_review=True`` o Director directo).
        - ``En revisión`` → ``Aprobada``.
        - ``En revisión DIRAE`` → ``Aprobada``.

        Para practicas estivales sin seguro escolar, se verifica la existencia
        de una excepcion administrativa solo cuando la transicion termina en
        ``Aprobada``. La excepcion no modifica el requisito institucional; solo
        habilita esa aprobacion.

        Args:
            internship_id: Identificador de la practica a aprobar.
            actor: Usuario autenticado con rol autorizado.
            comment: Comentario opcional registrado en el historial.
            skip_review: Si es ``True``, aprueba directamente desde ``Pendiente``
                omitiendo ``En revisión``.

        Returns:
            La entidad ``Internship`` con su nuevo estado.

        Raises:
            HTTPException 403: Si el actor no tiene permiso ``approve``.
            HTTPException 404: Si la practica no existe.
            HTTPException 409: Si el estado es terminal, la transicion no esta
                permitida, o la practica es estival sin seguro ni excepcion.
        """
        logger.info("Procesando aprobación para práctica ID: %s por actor ID: %s (skip_review=%s)", 
                    internship_id, actor.id, skip_review)
        self._require_action(actor, "approve")
        internship = await self._get_or_404(internship_id)
        current_title = self._status_title_or_default(internship.status)

        if current_title in TERMINAL_STATES:
            logger.warning("Intento de aprobar práctica ID: %s fallido. Ya está en estado terminal: %s", internship_id, current_title)
            raise HTTPException(
                status_code=409,
                detail=f"No se puede operar sobre una práctica en estado terminal: {current_title}.",
            )

        if internship.internship_type == PracticeTypeEnum.practice_1:
            passed = await self._has_passed_induction(internship.user_id)
            if not passed:
                logger.warning("Bloqueo de aprobación: Práctica ID: %s de tipo I no registra inducción obligatoria", internship_id)
                raise HTTPException(
                    status_code=409,
                    detail="La inducción es un requisito absoluto e inexceptuable para la Práctica de Estudio I. "
                           "No se puede tramitar la aprobación administrativa sin este prerrequisito.",
                )

        await self._check_sequentiality_or_exception(internship)
        await self._check_thesis_sequentiality(internship)
        await self._check_parallel_course_or_exception(internship)

        user_roles = {r.role.name for r in actor.roles}

        if current_title == PENDING_STATUS_TITLE:
            if skip_review or "Director de carrera" in user_roles:
                next_title = APPROVED_STATUS_TITLE
            else:
                next_title = IN_REVIEW_STATUS_TITLE
        elif current_title in (IN_REVIEW_STATUS_TITLE, IN_REVIEW_DIRAE_STATUS_TITLE):
            next_title = APPROVED_STATUS_TITLE
        else:
            logger.warning("El estado actual '%s' de la práctica ID: %s no acepta transicionar hacia aprobación", current_title, internship_id)
            raise HTTPException(
                status_code=409,
                detail=f"El estado actual '{current_title}' no permite aprobación.",
            )

        if next_title == APPROVED_STATUS_TITLE:
            await self._check_school_insurance_or_exception(internship)

        try:
            self._validate_status_transition(current_title, next_title)
        except ValueError as e:
            logger.error("Transición inválida en flujo de aprobación: %s", str(e))
            raise HTTPException(status_code=409, detail=str(e))

        result = await self._do_transition(
            internship=internship,
            new_status_title=next_title,
            actor_id=actor.id,
            reason=comment,
            metadata={"action": "approve", "skip_review": skip_review},
        )

        if next_title == APPROVED_STATUS_TITLE:
            await self._sync_academic_requirement_on_approval(result, actor)

        logger.info("Práctica ID: %s transicionada con éxito a '%s'. Despachando notificación...", result.id, next_title)
        await self._dispatch_notification(
            build_internship_approved_notification(
                recipient_user_id=result.user_id,
                recipient_email=result.student.email if result.student else None,
                internship_id=result.id,
                org_name=result.org_name,
            ),
        )

        return result
    
    async def reject(
        self,
        internship_id: int,
        actor: User,
        comment: str | None,
    ) -> Internship:
        """Rechaza de forma definitiva una solicitud de practica.

        await self._dispatch_notification(
            build_internship_approved_notification(
                recipient_user_id=result.user_id,
                recipient_email=result.student.email if result.student else None,
                internship_id=result.id,
                org_name=result.org_name,
            ),
        )

        return result

        Valida que el actor posea los permisos de rechazo y exige un motivo
        obligatorio. No permite modificar practicas en estados terminales.

        Args:
            internship_id: Identificador unico de la practica.
            actor: Usuario que ejecuta el rechazo.
            comment: Motivo obligatorio del rechazo.

        Returns:
            La entidad ``Internship`` transicionada al estado ``Rechazada``.

        Raises:
            HTTPException 400: Si no se proporciona comentario.
            HTTPException 403: Si el actor no tiene permiso ``reject``.
            HTTPException 404: Si la practica no existe.
            HTTPException 409: Si la practica esta en estado terminal.
        """
        logger.info("Procesando rechazo para práctica ID: %s por actor ID: %s", internship_id, actor.id)
        self._require_action(actor, "reject")
        self._require_comment(comment, "reject")
        internship = await self._get_or_404(internship_id)
        current_title = self._status_title_or_default(internship.status)

        if current_title in TERMINAL_STATES:
            logger.warning("Intento de rechazar práctica ID: %s fallido. Ya está en estado terminal: %s", internship_id, current_title)
            raise HTTPException(
                status_code=409,
                detail=f"No se puede rechazar una práctica en estado terminal: {current_title}.",
            )

        result = await self._do_transition(
            internship=internship,
            new_status_title=REJECTED_STATUS_TITLE,
            actor_id=actor.id,
            reason=comment,
            metadata={"action": "reject"},
        )

        logger.info("Práctica ID: %s rechazada de forma definitiva. Despachando notificación...", result.id)
        await self._dispatch_notification(
            build_internship_rejected_notification(
                recipient_user_id=result.user_id,
                recipient_email=result.student.email if result.student else None,
                internship_id=result.id,
                org_name=result.org_name,
                reason=comment,
            ),
        )

        return result
    
    
    async def derive(
        self,
        internship_id: int,
        actor: User,
        comment: str | None,
    ) -> Internship:
        """Deriva la practica hacia revision por DIRAE.

        Requiere permiso ``derive`` y comentario obligatorio. No permite
        derivar practicas en estados terminales.

        Args:
            internship_id: Identificador unico de la practica.
            actor: Usuario encargado de derivar (ej. Secretaria de Carrera).
            comment: Comentario obligatorio para la derivacion.

        Returns:
            La entidad ``Internship`` actualizada al estado ``En revisión DIRAE``.

        Raises:
            HTTPException 400: Si no se proporciona comentario.
            HTTPException 403: Si el actor no tiene permiso ``derive``.
            HTTPException 404: Si la practica no existe.
            HTTPException 409: Si la practica esta en estado terminal.
        """
        logger.info("Procesando derivación a DIRAE para práctica ID: %s por actor ID: %s", internship_id, actor.id)
        self._require_action(actor, "derive")
        self._require_comment(comment, "derive")
        internship = await self._get_or_404(internship_id)
        current_title = self._status_title_or_default(internship.status)

        if current_title in TERMINAL_STATES:
            logger.warning("Intento de derivar práctica ID: %s fallido. Ya está en estado terminal: %s", internship_id, current_title)
            raise HTTPException(
                status_code=409,
                detail=f"No se puede derivar una práctica en estado terminal: {current_title}.",
            )

        result = await self._do_transition(
            internship=internship,
            new_status_title=IN_REVIEW_DIRAE_STATUS_TITLE,
            actor_id=actor.id,
            reason=comment,
            metadata={"action": "derive"},
        )

        logger.info("Práctica ID: %s derivada correctamente a DIRAE. Despachando notificación...", result.id)
        await self._dispatch_notification(
            build_internship_derived_notification(
                recipient_user_id=result.user_id,
                recipient_email=result.student.email if result.student else None,
                internship_id=result.id,
                org_name=result.org_name,
                reason=comment,
            ),
        )

        return result

    async def update_admin_fields(
        self,
        internship_id: int,
        actor: User,
        payload: InternshipAdminUpdateRequest,
    ) -> Internship:
        """Actualiza campos editables de una practica con trazabilidad.

        Args:
            internship_id: Identificador de la practica a corregir.
            actor: Usuario administrativo que ejecuta la correccion.
            payload: Campos editables y motivo obligatorio.

        Returns:
            La entidad ``Internship`` actualizada.

        Raises:
            HTTPException 400: Si falta motivo, no hay campos o los datos son
                inconsistentes.
            HTTPException 403: Si el actor no tiene permiso ``admin_edit``.
            HTTPException 404: Si la practica no existe.
            HTTPException 409: Si la practica esta anulada o en estado terminal.
        """

        self._require_action(actor, "admin_edit")
        internship = await self._get_or_404(internship_id)
        reason = payload.reason.strip()

        if not reason:
            raise HTTPException(
                status_code=400,
                detail="El motivo de edición es obligatorio.",
            )

        self._require_editable_internship(internship, action_label="editar")

        updates = payload.model_dump(exclude={"reason"}, exclude_none=True)
        if not updates:
            raise HTTPException(
                status_code=400,
                detail="Debe informar al menos un campo editable.",
            )

        if "amount" in updates and updates["amount"] < 0:
            raise HTTPException(
                status_code=400,
                detail="El monto no puede ser negativo.",
            )

        start_date = updates.get("start_date", internship.start_date)
        end_date = updates.get("end_date", internship.end_date)
        if end_date < start_date:
            raise HTTPException(
                status_code=400,
                detail="La fecha de término no puede ser anterior a la fecha de inicio.",
            )

        return await self.internship_repository.update_internship_admin_fields_with_history(
            internship=internship,
            updates=updates,
            actor_id=actor.id,
            reason=reason,
            changed_fields=list(updates.keys()),
        )

    async def cancel(
        self,
        internship_id: int,
        actor: User,
        reason: str,
    ) -> Internship:
        """Anula logicamente una practica con motivo y trazabilidad.

        Args:
            internship_id: Identificador de la practica a anular.
            actor: Usuario administrativo que ejecuta la anulacion.
            reason: Motivo obligatorio de anulacion.

        Returns:
            La entidad ``Internship`` anulada logicamente.

        Raises:
            HTTPException 400: Si falta el motivo.
            HTTPException 403: Si el actor no tiene permiso ``cancel``.
            HTTPException 404: Si la practica no existe.
            HTTPException 409: Si la practica ya esta anulada o en estado terminal.
        """

        self._require_action(actor, "cancel")
        internship = await self._get_or_404(internship_id)
        clean_reason = reason.strip()

        if not clean_reason:
            raise HTTPException(
                status_code=400,
                detail="El motivo de anulación es obligatorio.",
            )

        self._require_editable_internship(internship, action_label="anular")

        return await self.internship_repository.cancel_internship_with_history(
            internship=internship,
            actor_id=actor.id,
            reason=clean_reason,
        )

    async def get_student_action_availability(
        self,
        internship_id: int,
        actor: User,
    ) -> StudentInternshipActionAvailabilityResponse:
        """Obtiene disponibilidad de correccion/anulacion para el propietario.

        Args:
            internship_id: Identificador de la practica.
            actor: Estudiante autenticado que consulta sus acciones.

        Returns:
            Disponibilidad y razones estables para que el frontend oculte
            acciones no permitidas.

        Raises:
            HTTPException 403: Si el actor no es propietario de la practica.
            HTTPException 404: Si la practica no existe.
        """

        internship = await self._get_or_404(internship_id)
        self._require_student_owner(internship, actor)

        return await self._build_student_action_availability(internship)

    async def update_student_fields(
        self,
        internship_id: int,
        actor: User,
        payload: StudentInternshipUpdateRequest,
    ) -> Internship:
        """Corrige una solicitud reciente desde el estudiante propietario.

        Args:
            internship_id: Identificador de la practica.
            actor: Estudiante propietario.
            payload: Campos permitidos y motivo obligatorio de correccion.

        Returns:
            La practica actualizada.

        Raises:
            HTTPException 400: Si falta motivo o no hay campos para corregir.
            HTTPException 403: Si el actor no es propietario.
            HTTPException 404: Si la practica no existe.
            HTTPException 409: Si el estado, ventana o historial lo bloquean.
        """

        internship = await self._get_or_404(internship_id)
        self._require_student_owner(internship, actor)
        await self._require_student_action_available(
            internship,
            action_label="corregir",
        )

        reason = payload.reason.strip()
        if not reason:
            raise HTTPException(
                status_code=400,
                detail="El motivo de corrección es obligatorio.",
            )

        updates = payload.model_dump(exclude={"reason"}, exclude_none=True)
        if not updates:
            raise HTTPException(
                status_code=400,
                detail="Debe informar al menos un campo editable.",
            )

        if (
            "internship_type" in updates
            and updates["internship_type"] != internship.internship_type
            and internship.blocks_new_registration
        ):
            await self._require_no_blocking_internship_type(
                user_id=actor.id,
                internship_type=updates["internship_type"],
                exclude_internship_id=internship.id,
            )

        start_date = updates.get("start_date", internship.start_date)
        end_date = updates.get("end_date", internship.end_date)
        if end_date < start_date:
            raise HTTPException(
                status_code=400,
                detail="La fecha de término no puede ser anterior a la fecha de inicio.",
            )

        try:
            return await self.internship_repository.update_internship_admin_fields_with_history(
                internship=internship,
                updates=updates,
                actor_id=actor.id,
                reason=reason,
                changed_fields=list(updates.keys()),
                action="student_update",
            )
        except IntegrityError:
            await self.internship_repository.rollback()
            if "internship_type" in updates:
                await self._require_no_blocking_internship_type(
                    user_id=actor.id,
                    internship_type=updates["internship_type"],
                    exclude_internship_id=internship.id,
                )
            raise

    async def cancel_by_student(
        self,
        internship_id: int,
        actor: User,
        reason: str,
    ) -> Internship:
        """Anula una solicitud reciente desde el estudiante propietario.

        Args:
            internship_id: Identificador de la practica.
            actor: Estudiante propietario.
            reason: Motivo obligatorio de anulacion.

        Returns:
            La practica marcada como anulada.

        Raises:
            HTTPException 400: Si falta el motivo.
            HTTPException 403: Si el actor no es propietario.
            HTTPException 404: Si la practica no existe.
            HTTPException 409: Si el estado, ventana o historial lo bloquean.
        """

        internship = await self._get_or_404(internship_id)
        self._require_student_owner(internship, actor)
        await self._require_student_action_available(
            internship,
            action_label="anular",
        )

        clean_reason = reason.strip()
        if not clean_reason:
            raise HTTPException(
                status_code=400,
                detail="El motivo de anulación es obligatorio.",
            )

        return await self.internship_repository.cancel_internship_with_history(
            internship=internship,
            actor_id=actor.id,
            reason=clean_reason,
            action="student_cancel",
        )

    def _raise_duplicate_internship_type(
        self,
        internship: Internship,
    ) -> None:
        """Responde con detalle estable cuando existe una solicitud bloqueante."""

        detail = DuplicateInternshipTypeDetail(
            code="duplicate_internship_type",
            existing_internship_id=internship.id,
            internship_type=internship.internship_type,
            existing_status=self._status_title_or_default(internship.status),
            message=(
                "Ya existe una solicitud vigente para este tipo de práctica. "
                "Revisa el registro existente antes de crear una nueva solicitud."
            ),
        )
        raise HTTPException(
            status_code=409,
            detail=detail.model_dump(mode="json"),
        )

    async def _require_no_blocking_internship_type(
        self,
        user_id: int,
        internship_type: PracticeTypeEnum,
        exclude_internship_id: int | None = None,
    ) -> None:
        """Valida que no exista otro registro bloqueante para el tipo."""

        blocking_internship = (
            await self.internship_repository.get_blocking_internship_for_registration(
                user_id=user_id,
                internship_type=internship_type,
                exclude_internship_id=exclude_internship_id,
            )
        )
        if blocking_internship is not None:
            self._raise_duplicate_internship_type(blocking_internship)

    def _require_editable_internship(
        self,
        internship: Internship,
        action_label: str,
    ) -> None:
        """Bloquea operaciones administrativas sobre practicas cerradas."""

        if internship.is_cancelled:
            raise HTTPException(
                status_code=409,
                detail=f"No se puede {action_label} una práctica anulada.",
            )

        current_title = self._status_title_or_default(internship.status)
        if current_title in TERMINAL_STATES:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"No se puede {action_label} una práctica en estado "
                    f"terminal: {current_title}."
                ),
            )

    def _require_student_owner(
        self,
        internship: Internship,
        actor: User,
    ) -> None:
        """Valida ownership estricto para acciones del estudiante."""

        if internship.user_id != actor.id:
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions",
            )

    async def _require_student_action_available(
        self,
        internship: Internship,
        action_label: str,
    ) -> None:
        """Bloquea correccion/anulacion cuando backend no la permite."""

        availability = await self._build_student_action_availability(internship)
        allowed = availability.can_update if action_label == "corregir" else availability.can_cancel
        if allowed:
            return

        raise HTTPException(
            status_code=409,
            detail={
                "message": f"No se puede {action_label} esta solicitud.",
                "reasons": availability.reasons,
                "editable_until": availability.editable_until.isoformat()
                if availability.editable_until is not None
                else None,
            },
        )

    async def _build_student_action_availability(
        self,
        internship: Internship,
    ) -> StudentInternshipActionAvailabilityResponse:
        """Construye razones estables para habilitar u ocultar acciones."""

        reasons = []
        editable_until = self._get_student_edit_deadline(internship)

        if internship.is_cancelled:
            reasons.append("internship_cancelled")

        current_title = self._status_title_or_default(internship.status)
        if current_title != PENDING_STATUS_TITLE:
            reasons.append("status_not_pending")

        if (
            editable_until is not None
            and datetime.now(UTC).replace(tzinfo=None) > editable_until
        ):
            reasons.append("window_expired")

        if await self._has_blocking_history_action(internship):
            reasons.append("administrative_action_exists")

        can_act = len(reasons) == 0
        return StudentInternshipActionAvailabilityResponse(
            can_update=can_act,
            can_cancel=can_act,
            editable_until=editable_until,
            reasons=reasons,
        )

    def _get_student_edit_deadline(
        self,
        internship: Internship,
    ) -> datetime | None:
        """Calcula el limite temporal de correccion reciente."""

        upload_date = getattr(internship, "upload_date", None)
        if upload_date is None:
            return None

        return upload_date + timedelta(hours=self.student_edit_window_hours)

    async def _has_blocking_history_action(
        self,
        internship: Internship,
    ) -> bool:
        """Detecta acciones administrativas previas sobre la solicitud."""

        history = await self.internship_repository.list_internship_status_history(
            internship_id=internship.id,
        )
        for entry in history:
            metadata = entry.metadata_json or {}
            action = metadata.get("action")
            if action not in STUDENT_ALLOWED_HISTORY_ACTIONS:
                return True

        return False

    async def _get_or_404(self, internship_id: int) -> Internship:
        """Busca una practica o lanza 404 si no existe.

        Args:
            internship_id: Identificador de la practica requerida.

        Returns:
            La entidad ``Internship`` recuperada.

        Raises:
            HTTPException 404: Si el repositorio devuelve ``None``.
        """
        internship = await self.internship_repository.get_internship_by_id(internship_id)
        if internship is None:
            logger.warning("Recuperación fallida: Práctica con ID %s no existe", internship_id)
            raise HTTPException(
                status_code=404,
                detail="Práctica no encontrada (Internship not found)",
            )
        return internship

    async def grant_exception(
        self,
        internship_id: int,
        actor: User,
        rule: str,
        reason: str,
    ) -> InternshipException:
        """Registra una excepcion administrativa sobre una regla de negocio.

        La excepcion permite que una practica continúe su flujo pese a no
        cumplir la regla indicada. No modifica el valor original del campo
        (ej. ``has_school_insurance`` permanece ``False``); solo habilita
        el procesamiento administrativo con trazabilidad completa.

        Solo aplica a practicas en estado no terminal. Una excepcion ya
        registrada para la misma regla en la misma practica es idempotente:
        se retorna la existente sin crear un duplicado.

        Args:
            internship_id: Identificador de la practica.
            actor: Usuario que autoriza la excepcion.
            rule: Nombre canonico de la regla a exceptuar
                (ej. ``"school_insurance"``).
            reason: Justificacion obligatoria de la excepcion.

        Returns:
            La entidad ``InternshipException`` creada o existente.

        Raises:
            HTTPException 400: Si la regla indicada no es exceptuable.
            HTTPException 403: Si el actor no tiene permiso ``grant_exception``.
            HTTPException 404: Si la practica no existe.
            HTTPException 409: Si la practica esta en estado terminal.
        """
        logger.info("Solicitud para conceder excepción sobre regla '%s' en práctica ID: %s por actor ID: %s", 
                    rule, internship_id, actor.id)
        self._require_action(actor, "grant_exception")

        if rule not in EXCEPTABLE_RULES:
            logger.warning("La regla '%s' no pertenece al conjunto de reglas exceptuables", rule)
            raise HTTPException(
                status_code=400,
                detail=f"La regla '{rule}' no admite excepción administrativa.",
            )

        internship = await self._get_or_404(internship_id)
        current_title = self._status_title_or_default(internship.status)

        if current_title in TERMINAL_STATES:
            logger.warning("Imposible aplicar excepción. Práctica ID: %s se encuentra en estado terminal (%s)", internship_id, current_title)
            raise HTTPException(
                status_code=409,
                detail=f"No se puede registrar una excepción sobre una práctica en estado terminal: {current_title}.",
            )

        existing = await self.internship_repository.get_exception_by_rule(
            internship_id=internship_id,
            rule=rule,
        )
        if existing is not None:
            logger.info("Excepción para la regla '%s' en la práctica ID: %s ya existía (Idempotencia)", rule, internship_id)
            return existing

        result = await self.internship_repository.create_exception(
            internship_id=internship_id,
            rule=rule,
            reason=reason,
            authorized_by=actor.id,
        )
        logger.info("Excepción '%s' creada con éxito para práctica ID: %s", rule, internship_id)
        return result
    
    async def _check_school_insurance_or_exception(
        self,
        internship: Internship,
    ) -> None:
        """Verifica que la practica cumpla la regla de seguro escolar o tenga excepcion vigente.

        Para practicas en periodo estival (``Verano`` o ``Invierno``), consulta
        el prerrequisito institucional vigente del estudiante. Si no esta
        completado, la aprobacion solo se permite si existe una excepcion
        administrativa para la regla ``"school_insurance"``.

        Args:
            internship: Practica a verificar.

        Raises:
            HTTPException 409: Si la practica es estival, no tiene seguro
                y tampoco tiene excepcion administrativa registrada.
        """
        is_seasonal = internship.internship_period.value in SEASONAL_PERIODS
        if not is_seasonal:
            return

        insurance_requirement = (
            await self.internship_repository.get_student_requirement(
                user_id=internship.user_id,
                requirement="school_insurance",
            )
        )
        has_current_insurance = (
            insurance_requirement is not None
            and insurance_requirement.is_completed
        )
        internship.has_school_insurance = has_current_insurance

        if has_current_insurance:
            return

        logger.info("Evaluando seguro escolar estival requerido para práctica ID: %s en periodo: %s", 
                    internship.id, internship.internship_period)
        existing = await self.internship_repository.get_exception_by_rule(
            internship_id=internship.id,
            rule="school_insurance",
        )
        if existing is None:
            logger.warning("Bloqueo por matriz de riesgo: Práctica estival ID: %s no cuenta con seguro ni excepción registrada", internship.id)
            raise HTTPException(
                status_code=409,
                detail={
                    "rule": "school_insurance",
                    "message": (
                        "La práctica es estival y no cuenta con seguro escolar. "
                        "Se requiere una excepción administrativa registrada para continuar (D.S. 313)."
                    ),
                },
            )
        logger.info("Validación exitosa: Práctica estival ID: %s cuenta con una excepción administrativa vigente", internship.id)

    async def _check_sequentiality_or_exception(
        self,
        internship: Internship,
    ) -> None:
        """Verifica secuencialidad: Práctica II requiere Práctica I aprobada o excepción.

        La fuente de verdad es ``StudentInternshipRequirement`` (requisito académico),
        no el estado de una ``Internship`` individual. Si el requisito académico
        de Práctica de Estudio I está aprobado, la secuencialidad se cumple.

        Raises:
            HTTPException 409: Si no se cumple la secuencialidad y no hay
                excepción vigente.
        """
        if internship.internship_type != PracticeTypeEnum.practice_2:
            return

        req = await self.internship_repository.get_academic_requirement(
            user_id=internship.user_id,
            practice_type=PracticeTypeEnum.practice_1.value,
        )
        if req is not None and req.status == "Aprobada":
            return

        existing = await self.internship_repository.get_exception_by_rule(
            internship_id=internship.id,
            rule="sequentiality",
        )
        if existing is not None:
            logger.info(
                "Excepción de secuencialidad vigente para práctica ID: %s",
                internship.id,
            )
            return

        logger.warning(
            "Bloqueo por secuencialidad: Práctica II ID: %s sin Práctica I aprobada "
            "ni excepción registrada",
            internship.id,
        )
        raise HTTPException(
            status_code=409,
            detail={
                "rule": "sequentiality",
                "message": (
                    "La Práctica de Estudio II requiere que la Práctica de Estudio I "
                    "se encuentre aprobada. Si existe una causa justificada, un "
                    "actor administrativo autorizado puede registrar una excepción "
                    "de secuencialidad para continuar el trámite."
                ),
            },
        )

    async def _check_thesis_sequentiality(
        self,
        internship: Internship,
    ) -> None:
        """Verifica secuencialidad para Tesis: requiere Práctica II aprobada o excepción.

        Raises:
            HTTPException 409: Si no se cumple la secuencialidad y no hay
                excepción vigente.
        """
        if internship.internship_type != PracticeTypeEnum.thesis:
            return

        req = await self.internship_repository.get_academic_requirement(
            user_id=internship.user_id,
            practice_type=PracticeTypeEnum.practice_2.value,
        )
        if req is not None and req.status == "Aprobada":
            return

        existing = await self.internship_repository.get_exception_by_rule(
            internship_id=internship.id,
            rule="sequentiality_thesis",
        )
        if existing is not None:
            logger.info(
                "Excepción de secuencialidad para Tesis vigente en práctica ID: %s",
                internship.id,
            )
            return

        logger.warning(
            "Bloqueo por secuencialidad: Tesis ID: %s sin Práctica II aprobada "
            "ni excepción registrada",
            internship.id,
        )
        raise HTTPException(
            status_code=409,
            detail={
                "rule": "sequentiality_thesis",
                "message": (
                    "La Tesis requiere que la Práctica de Estudio II se encuentre "
                    "aprobada. Si existe una causa justificada, un actor "
                    "administrativo autorizado puede registrar una excepción "
                    "de secuencialidad para continuar el trámite."
                ),
            },
        )

    async def _check_parallel_course_or_exception(
        self,
        internship: Internship,
    ) -> None:
        """Verifica regla de ramo en paralelo para Práctica Controlada.

        La Práctica Controlada requiere que los co-requisitos (ramos en
        paralelo) estén resueltos. Como el sistema aún no modela la malla
        curricular, se asume que hay co-requisitos pendientes y se exige
        una excepción administrativa ``"parallel_course"`` para permitir
        el avance.

        Raises:
            HTTPException 409: Si no existe una excepción de ramo en
                paralelo registrada.
        """
        if internship.internship_type != PracticeTypeEnum.controlled_practice:
            return

        existing = await self.internship_repository.get_exception_by_rule(
            internship_id=internship.id,
            rule="parallel_course",
        )
        if existing is not None:
            logger.info(
                "Excepción de ramo en paralelo vigente para práctica controlada ID: %s",
                internship.id,
            )
            return

        logger.warning(
            "Bloqueo por ramo en paralelo: Práctica Controlada ID: %s sin excepción registrada",
            internship.id,
        )
        raise HTTPException(
            status_code=409,
            detail={
                "rule": "parallel_course",
                "message": (
                    "La Práctica Controlada requiere que los co-requisitos "
                    "(ramos en paralelo) estén resueltos. Si existe una causa "
                    "justificada, un actor administrativo autorizado puede "
                    "registrar una excepción de ramo en paralelo para continuar "
                    "el trámite."
                ),
            },
        )

    async def _sync_academic_requirement_on_approval(
        self,
        internship: Internship,
        actor: User,
    ) -> None:
        """Sincroniza ``StudentInternshipRequirement`` al aprobar una práctica.

        Si el requisito académico no existe, se crea con estado ``Aprobada``.
        Si existe, se actualiza su estado. La fuente de verdad transaccional
        sigue siendo ``Internship.status``; este método es un espejo para
        habilitar consultas de secuencialidad sin depender del estado
        administrativo de prácticas individuales.
        """
        try:
            await self.internship_repository.upsert_academic_requirement_status(
                user_id=internship.user_id,
                practice_type=internship.internship_type.value,
                new_status="Aprobada",
                updated_by=actor.id,
            )
            logger.info(
                "Requisito académico sincronizado para práctica ID: %s, tipo: %s",
                internship.id,
                internship.internship_type.value,
            )
        except Exception:
            logger.exception(
                "Fallo al sincronizar requisito académico para práctica ID: %s. "
                "La práctica ya fue aprobada; la sincronización puede reintentarse "
                "manualmente.",
                internship.id,
            )

    async def _dispatch_notification(self, notification) -> None:
        """Despacha una notificacion a traves del servicio de notificaciones.

        Si el servicio de notificaciones no esta configurado, la operacion se
        ignora silenciosamente. Los errores de notificacion no interrumpen el
        flujo principal de negocio.

        Args:
            notification: Entidad `Notification` construida por un helper de eventos.
        """

        if self.notification_service is None:
            return

        try:
            await self.notification_service.create_and_dispatch(notification)
        except Exception:
            logger.warning(
                "Fallo al despachar notificacion (event=%s). "
                "El flujo de negocio continua normalmente.",
                notification.event_type,
                exc_info=True,
            )

    async def get_active_induction_content(
        self,
    ) -> InductionContentVersionResponse | None:
        """Retorna la versión activa y publicada del contenido de inducción.

        Returns:
            ``InductionContentVersionResponse`` con videos y preguntas,
            o ``None`` si no hay contenido publicado activo.
        """
        content = await self.internship_repository.get_active_induction_content()
        if content is None:
            return None
        return InductionContentVersionResponse.model_validate(content)

    async def submit_induction_attempt(
        self,
        user_id: int,
        payload: InductionAttemptRequest,
    ) -> InductionAttemptResponse:
        """Evalúa y registra un intento de cuestionario de inducción.

        Recupera la versión activa de contenido, compara las respuestas
        del estudiante contra las correctas, calcula el puntaje y
        persiste el resultado. Si el puntaje es igual o superior al
        mínimo configurado, el intento se marca como aprobado.

        Args:
            user_id: Identificador del estudiante.
            payload: Respuestas del cuestionario.

        Returns:
            ``InductionAttemptResponse`` con el resultado del intento.

        Raises:
            HTTPException 409: Si no hay contenido activo publicado.
        """
        content = await self.internship_repository.get_active_induction_content()
        if content is None:
            raise HTTPException(
                status_code=409,
                detail="No hay contenido de inducción activo publicado.",
            )

        questions = {q.id: q for q in content.questions}
        score = 0
        for question_id, answer in payload.answers.items():
            question = questions.get(question_id)
            if question is None:
                continue
            if question.correct_answer == answer:
                score += 1

        passed = score >= content.min_score
        attempt = InductionAttempt(
            user_id=user_id,
            content_version_id=content.id,
            answers=payload.answers,
            score=score,
            passed=passed,
        )
        created = await self.internship_repository.create_induction_attempt(attempt)
        return InductionAttemptResponse.model_validate(created)

    async def _has_passed_induction(
        self,
        user_id: int | None,
    ) -> bool:
        """Verifica si un estudiante ha aprobado la inducción obligatoria.

        Primero consulta ``StudentRegistrationRequirement``; si no existe
        o está marcado como no completado, consulta el último intento
        aprobado en ``InductionAttempt``.

        Args:
            user_id: Identificador del estudiante.

        Returns:
            ``True`` si el estudiante cumple con la inducción.
        """
        if user_id is None:
            return False

        req = await self.internship_repository.get_student_requirement(
            user_id=user_id,
            requirement="induction",
        )
        if req is not None and req.is_completed:
            return True

        passed_attempt = await self.internship_repository.get_passed_induction_attempt(
            user_id=user_id,
        )
        return passed_attempt is not None

    async def get_registration_eligibility(
        self,
        user_id: int,
        internship_period: PracticePeriodEnum | None = None,
        internship_type: PracticeTypeEnum | None = None,
    ) -> RegistrationEligibilityResponse:
        """Evalúa requisitos para formalizar una solicitud de práctica.

        La ausencia de seguro solo bloquea periodos estivales y la inducción
        solo bloquea la Práctica de Estudio I.

        Args:
            user_id: Identificador del estudiante.
            internship_period: Periodo de la práctica que se desea evaluar.
            internship_type: Tipo de práctica que se desea evaluar.

        Returns:
            ``RegistrationEligibilityResponse`` con el estado de cada
            prerrequisito y el siguiente paso sugerido.
        """
        insurance_req = await self.internship_repository.get_student_requirement(
            user_id=user_id,
            requirement="school_insurance",
        )
        has_insurance = insurance_req is not None and insurance_req.is_completed

        has_induction = await self._has_passed_induction(user_id)

        internships = await self.internship_repository.list_internships_by_user(user_id)

        has_school_insurance_exception = any(
            any(exc.rule == "school_insurance" for exc in (internship.exceptions or []))
            for internship in internships
        )

        has_approved_practice_1 = any(
            inn.status is not None
            and inn.status.title in APPROVED_STATUS_TITLE_SET
            and inn.internship_type == PracticeTypeEnum.practice_1
            for inn in internships
        )

        sequentiality_blocked = not has_approved_practice_1

        has_sequentiality_exception = any(
            any(exc.rule == "sequentiality" for exc in (internship.exceptions or []))
            for internship in internships
        )
        blocking_internship = None
        if internship_type is not None:
            blocking_internship = (
                await self.internship_repository.get_blocking_internship_for_registration(
                    user_id=user_id,
                    internship_type=internship_type,
                )
            )
        has_blocking_internship = blocking_internship is not None

        insurance_blocked = (
            internship_period is not None
            and internship_period.value in SEASONAL_PERIODS
            and not has_insurance
        )
        induction_blocked = (
            internship_type == PracticeTypeEnum.practice_1
            and not has_induction
        )
        blocked = insurance_blocked or induction_blocked
        next_step = (
            "Puede crear la solicitud y continuar con su revisión administrativa."
        )

        if has_blocking_internship:
            next_step = (
                "Ya existe una solicitud vigente para este tipo de práctica. "
                "Revisa el registro existente antes de crear una nueva solicitud."
            )
        elif insurance_blocked:
            next_step = (
                "Debe registrar el seguro escolar ante la unidad correspondiente "
                "o contar con una excepción antes de aprobar la práctica estival."
            )
        elif induction_blocked:
            next_step = (
                "Debe completar la inducción obligatoria y aprobar el cuestionario "
                "antes de tramitar la aprobación de la Práctica de Estudio I."
            )

        return RegistrationEligibilityResponse(
            has_school_insurance=has_insurance,
            has_induction=has_induction,
            has_school_insurance_exception=has_school_insurance_exception,
            has_approved_practice_1=has_approved_practice_1,
            sequentiality_blocked=sequentiality_blocked,
            has_sequentiality_exception=has_sequentiality_exception,
            has_blocking_internship=has_blocking_internship,
            blocking_internship_id=blocking_internship.id
            if blocking_internship is not None
            else None,
            blocking_internship_status=self._status_title_or_default(
                blocking_internship.status,
            )
            if blocking_internship is not None
            else None,
            can_create_request=not has_blocking_internship,
            blocked=blocked,
            next_step=next_step,
        )

    async def _dispatch_internship_created_notifications(
        self,
        internship: Internship,
    ) -> None:
        """Notifica a revisores cuando un estudiante registra una practica."""

        if self.notification_service is None:
            return

        recipients = await self.internship_repository.list_users_by_roles(
            INTERNSHIP_CREATION_NOTIFICATION_ROLES,
        )
        for recipient in recipients:
            await self._dispatch_notification(
                build_internship_created_notification(
                    recipient_user_id=recipient.id,
                    recipient_email=recipient.email,
                    internship_id=internship.id,
                    org_name=internship.org_name,
                    student_user_id=internship.user_id,
                ),
            )
