"""Servicios de negocio para practicas.

Este modulo define `InternshipService`, encargado de coordinar los casos de uso
del modulo `internships` y delegar operaciones de persistencia al repositorio.
"""
from fastapi import HTTPException

from app.modules.internships.models.internship_model import Internship
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
STATUS_LABEL_TO_DASHBOARD_STATUS: dict[str, DashboardInternshipStatus] = {
    "Pendiente": "submitted",
    "En revisión": "in_review",
    "Aprobada": "approved",
    "Rechazada": "rejected",
    "Reprobada": "rejected",
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

        internship = Internship(
            **internship_data.model_dump(),
            user_id=user_id,
        )

        return await self.internship_repository.create_internship(internship)

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
            