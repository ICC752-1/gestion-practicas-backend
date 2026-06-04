"""Servicios de negocio para practicas.

Este modulo define `InternshipService`, encargado de coordinar los casos de uso
del modulo `internships` y delegar operaciones de persistencia al repositorio.
"""
from fastapi import HTTPException

from typing import Any

from app.modules.internships.models.current_state_model import CurrentState
from app.modules.internships.models.internship_model import Internship
from app.modules.internships.models.internship_status_history_model import (
    InternshipStatusHistory,
)
from app.modules.internships.repositories.internship_repository import (
    InternshipRepository,
)
from app.modules.internships.schemas.internship_schema import (
    DashboardInternshipStatus,
    InternshipCreateRequest,
    InternshipDashboardListItem,
    InternshipDashboardStatsResponse,
    InternshipDashboardStudentResponse,
)
from app.modules.auth.models.user_model import User

DEFAULT_DASHBOARD_STATUS_LABEL = "Pendiente"
PENDING_STATUS_TITLE = "Pendiente"
IN_REVIEW_STATUS_TITLE = "En revisión"
APPROVED_STATUS_TITLE = "Aprobada"
REJECTED_STATUS_TITLE = "Rechazada"
LEGACY_REJECTED_STATUS_TITLE = "Reprobada"
IN_REVIEW_DIRAE_STATUS_TITLE = "En revisión DIRAE"
TERMINAL_STATES = {APPROVED_STATUS_TITLE, REJECTED_STATUS_TITLE, LEGACY_REJECTED_STATUS_TITLE}

INITIAL_HISTORY_REASON = "Registro inicial de práctica"
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
    "Encargado de practica": ["approve", "reject"],
    "Director de carrera": ["approve", "reject"],
    "Secretaria de Carrera": ["derive"]
}

class InternshipService:
    """Orquesta casos de uso relacionados con practicas.

    Attributes:
        internship_repository: Repositorio de acceso a datos para practicas.
    """

    def __init__(self, internship_repository: InternshipRepository) -> None:
        """Inicializa el servicio con sus dependencias.

        Args:
            internship_repository: Repositorio para consultar y persistir
                practicas.
        """

        self.internship_repository = internship_repository

    async def create_internship(
        self,
        internship_data: InternshipCreateRequest,
        user_id: int,
    ) -> Internship:
        """Crea una practica asociada a un usuario.

        Convierte el schema de entrada en una entidad ORM y asigna el
        identificador del estudiante autenticado como propietario.

        Args:
            internship_data: Datos validados para crear la practica.
            user_id: Identificador entero del usuario propietario.

        Returns:
            Entidad `Internship` persistida.
        """

        initial_status = await self._get_required_state(PENDING_STATUS_TITLE)
        internship = Internship(
            **internship_data.model_dump(),
            user_id=user_id,
            status_id=initial_status.id,
        )

        return await self.internship_repository.create_internship_with_history(
            internship=internship,
            initial_status=initial_status,
            actor_id=user_id,
            reason=INITIAL_HISTORY_REASON,
            metadata={"event": "internship_created"},
        )

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
        """Aprueba una práctica sin imponer una cadena Encargado -> Director.

        El flujo no es secuencial obligatorio: cualquier actor con permiso
        `approve` puede aprobar desde ``Pendiente`` o ``En revisión``. El estado
        ``En revisión`` queda como trazabilidad opcional, no como paso bloqueante.
        ``En revisión DIRAE`` se conserva solo como compatibilidad con registros
        existentes.

        Args:
            internship_id: Identificador único de la práctica a aprobar.
            actor: Entidad del usuario autenticado que ejecuta la acción.
            comment: Comentario u observación opcional que se registrará en el historial.
            skip_review: Bandera conservada por compatibilidad; la aprobación
                desde ``Pendiente`` ya es directa para roles autorizados.

        Returns:
            La entidad `Internship` actualizada con su nuevo estado y el registro
            de historial asociado.

        Raises:
            HTTPException 403: Si el actor no posee el permiso "approve" en sus roles.
            HTTPException 404: Si la práctica con el `internship_id` provisto no existe.
            HTTPException 409: Si el estado actual es terminal o si la transición
                solicitada no está permitida en `ALLOWED_STATUS_TRANSITIONS`.
        """
        self._require_action(actor, "approve")
        internship = await self._get_or_404(internship_id)
        current_title = self._status_title_or_default(internship.status)

        if current_title in TERMINAL_STATES:
            raise HTTPException(
                status_code=409,
                detail=f"No se puede operar sobre una práctica en estado terminal: {current_title}.",
            )

        if current_title in (
            PENDING_STATUS_TITLE,
            IN_REVIEW_STATUS_TITLE,
            IN_REVIEW_DIRAE_STATUS_TITLE,
        ):
            next_title = APPROVED_STATUS_TITLE
        else:
            raise HTTPException(
                status_code=409,
                detail=f"El estado actual '{current_title}' no permite aprobación.",
            )

        self._validate_status_transition(current_title, next_title)

        return await self._do_transition(
            internship=internship,
            new_status_title=next_title,
            actor_id=actor.id,
            reason=comment,
            metadata={"action": "approve", "skip_review": skip_review},
        )    

    async def reject(self, internship_id: int, actor: User, comment: str | None) -> Internship:
        """
        Rechaza de forma definitiva una solicitud de práctica.

        Valida que el actor posea los permisos de rechazo y exige de manera obligatoria 
        un motivo en el parámetro `comment`. No permite modificar prácticas en estados terminales.

        Args:
            internship_id: Identificador único de la práctica.
            actor: Usuario que ejecuta el rechazo.
            comment: Motivo obligatorio del rechazo de la práctica.

        Returns:
            La entidad `Internship` transicionada al estado 'Rechazada'.

        Raises:
            HTTPException: Con código de estado 409 si la práctica ya se encuentra 
                en un estado terminal.
        """
        
        self._require_action(actor, "reject")
        self._require_comment(comment, "reject")
        internship = await self._get_or_404(internship_id)
        current_title = self._status_title_or_default(internship.status)

        if current_title in TERMINAL_STATES:
            raise HTTPException(
                status_code=409,
                detail=f"No se puede rechazar una práctica en estado terminal: {current_title}.",
            )

        return await self._do_transition(
            internship=internship,
            new_status_title=REJECTED_STATUS_TITLE,
            actor_id=actor.id,
            reason=comment,
            metadata={"action": "reject"},
        )
    
    async def derive(self, internship_id: int, actor: User, comment: str | None) -> Internship:
        """
        Deriva el flujo de la práctica hacia la Dirección de Registro Académico Estudiantil (DIRAE).

        Requiere que el actor cuente con el permiso de derivación y que argumente la acción 
        mediante un comentario obligatorio.

        Args:
            internship_id: Identificador único de la práctica.
            actor: Usuario encargado de derivar el caso (ej. Secretaria de Carrera).
            comment: Comentario u observaciones obligatorias para la derivación.

        Returns:
            La entidad `Internship` actualizada al estado 'En revisión DIRAE'.

        Raises:
            HTTPException: Con código de estado 409 si la práctica está en un estado terminal.
        """
        self._require_action(actor, "derive")
        self._require_comment(comment, "derive")
        internship = await self._get_or_404(internship_id)
        current_title = self._status_title_or_default(internship.status)

        if current_title in TERMINAL_STATES:
            raise HTTPException(
                status_code=409,
                detail=f"No se puede derivar una práctica en estado terminal: {current_title}.",
            )

        return await self._do_transition(
            internship=internship,
            new_status_title=IN_REVIEW_DIRAE_STATUS_TITLE,
            actor_id=actor.id,
            reason=comment,
            metadata={"action": "derive"},
        )

    async def _get_or_404(self, internship_id: int) -> Internship:
        """
        Busca una práctica por su identificador o lanza un error si no existe.

        Método utilitario interno para asegurar la existencia de la entidad antes de operar.

        Args:
            internship_id: Identificador de la práctica requerida.

        Returns:
            La entidad `Internship` recuperada del repositorio.

        Raises:
            HTTPException: Con código de estado 404 si el repositorio devuelve `None`.
        """    
        internship = await self.internship_repository.get_internship_by_id(internship_id)
        if internship is None:
            raise HTTPException(status_code=404, detail="Práctica no encontrada (Internship not found)")
        return internship
            
