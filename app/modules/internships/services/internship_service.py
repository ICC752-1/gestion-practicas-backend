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
from app.modules.internships.models.current_state_model import CurrentState
from app.modules.auth.models.user_model import User

DEFAULT_DASHBOARD_STATUS_LABEL = "Pendiente"
PENDING_STATUS_TITLE = "Pendiente"
IN_REVIEW_STATUS_TITLE = "En revisión"
APPROVED_STATUS_TITLE = "Aprobada"
REJECTED_STATUS_TITLE = "Rechazada"
LEGACY_REJECTED_STATUS_TITLE = "Reprobada"
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
        APPROVED_STATUS_TITLE,
        REJECTED_STATUS_TITLE,
    },
    IN_REVIEW_STATUS_TITLE: {
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
    "Encargado de practica": ["approve_stage_1", "reject"],
    "Director de carrera": ["approve_stage_2", "reject"],
    "Secretaria de carrera": ["derive"]
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
        """Obtiene conteos agregados para el dashboard de coordinador/director."""

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
        allowed = set()
        for user_role in user.roles:
            role_name = user_role.role.name
            allowed.update(ROLE_PERMISSIONS.get(role_name, []))
        return allowed
    
    def _require_action(self, user: User, action: str) -> None:
        if action not in self._get_user_actions(user):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    def _require_comment(self, comment: str | None, action: str) -> None:
        if action in ("reject", "derive") and (not comment or not comment.strip()):
            raise HTTPException(
                status_code=400, 
                detail=f"El motivo/comentario es obligatorio para la acción: {action}"
            )

    def _register_audit_event(
        self, internship_id: int, action: str, actor_id: int, comment: str | None
    ) -> None:
        """
        STUB de integración con Tracking de 9.3.
        Mantiene la trazabilidad mínima requerida hasta la llegada del servicio real.
        """
        import logging
        logging.getLogger(__name__).info(
            "[TRACKING-STUB] internship=%s action=%s actor=%s comment=%s",
            internship_id, action, actor_id, comment,
        )

    async def approve(self, internship_id: int, actor: User, comment: str | None) -> Internship:
            internship = await self._get_or_404(internship_id)

            # Validación de transiciones inválidas (Control de flujo de estados)
            if internship.status is not None:
                if internship.status.title in ("Rechazada", "Reprobada"):
                    raise HTTPException(
                        status_code=409, 
                        detail="Transición inválida: No se puede aprobar una práctica rechazada/reprobada sin reapertura."
                    )
                if internship.status.title == "Aprobada":
                    raise HTTPException(
                        status_code=409, 
                        detail="La práctica ya se encuentra completamente aprobada."
                    )

            # Lógica de aprobación por Etapas / Roles
            if internship.status is None or internship.status.title == "Pendiente":
                self._require_action(actor, "approve_stage_1")
                next_title = "En revisión"
            elif internship.status.title == "En revisión":
                self._require_action(actor, "approve_stage_2")
                next_title = "Aprobada"
            else:
                raise HTTPException(status_code=409, detail="Estado actual no mapeado para aprobación")

            new_state = await self.internship_repository.get_state_by_title(next_title)
            internship.status_id = new_state.id
            
            await self.internship_repository.save(internship)
            self._register_audit_event(internship_id, "approve", actor.id, comment)
            return internship                   

    async def reject(self, internship_id: int, actor: User, comment: str | None) -> Internship:
            self._require_action(actor, "reject")
            self._require_comment(comment, "reject")
            internship = await self._get_or_404(internship_id)

            # Evitar re-rechazar si ya está en ese estado terminal
            if internship.status is not None and internship.status.title in ("Rechazada", "Reprobada"):
                raise HTTPException(status_code=409, detail="La práctica ya fue rechazada previamente.")

            new_state = await self.internship_repository.get_state_by_title("Rechazada")
            internship.status_id = new_state.id
            
            await self.internship_repository.save(internship)
            self._register_audit_event(internship_id, "reject", actor.id, comment)
            return internship

    async def derive(self, internship_id: int, actor: User, comment: str | None) -> Internship:
            self._require_action(actor, "derive")
            self._require_comment(comment, "derive")
            internship = await self._get_or_404(internship_id)

            # Evitar derivaciones desde estados inválidos
            if internship.status is not None and internship.status.title in ("Rechazada", "Reprobada", "Aprobada"):
                raise HTTPException(
                    status_code=409, 
                    detail=f"No se puede derivar una práctica en estado terminal: {internship.status.title}"
                )

            new_state = await self.internship_repository.get_state_by_title("En revisión DIRAE")
            internship.status_id = new_state.id
            
            await self.internship_repository.save(internship)
            self._register_audit_event(internship_id, "derive", actor.id, comment)
            return internship

    async def _get_or_404(self, internship_id: int) -> Internship:
            internship = await self.internship_repository.get_internship_by_id(internship_id)
            if internship is None:
                raise HTTPException(status_code=404, detail="Práctica no encontrada (Internship not found)")
            return internship
            

