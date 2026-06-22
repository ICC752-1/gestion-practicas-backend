"""Casos de uso para evaluaciones publicas de supervisores externos."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from app.core.config import config
from app.modules.auth.models.user_model import User
from app.modules.internships.models import Internship
from app.modules.internships.models.internship_model import CompletionStatusEnum
from app.modules.notifications.models.notification_model import (
    Notification,
    NotificationEventTypeEnum,
    NotificationStatusEnum,
)
from app.modules.notifications.services.notification_service import NotificationService
from app.modules.supervisor_evaluations.models.supervisor_evaluation_model import (
    SupervisorEvaluation,
    SupervisorEvaluationInvitation,
)
from app.modules.supervisor_evaluations.repositories.supervisor_evaluation_repository import (
    SupervisorEvaluationRepository,
)
from app.modules.supervisor_evaluations.schemas.supervisor_evaluation_schema import (
    SUPERVISOR_EVALUATION_CRITERIA,
    SupervisorAssignmentResponse,
    SupervisorEvaluationCriteriaResponse,
    SupervisorEvaluationInvitationResponse,
    SupervisorEvaluationPublicResponse,
    SupervisorEvaluationSubmitRequest,
    SupervisorEvaluationSubmitResponse,
)


INVITATION_TTL_DAYS = 14
ADMIN_ROLES = {"Encargado de practica", "Director de carrera"}
SUPERVISOR_ROLE = "Supervisor de practica"
APPROVED_INTERNSHIP_STATUS = "Aprobada"


class SupervisorEvaluationError(Exception):
    """Error funcional con codigo HTTP sugerido para el controlador."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _role_names(user: User) -> set[str]:
    return {user_role.role.name for user_role in user.roles}


def _student_name(internship: Internship) -> str:
    if internship.student is None:
        return "Estudiante"
    return f"{internship.student.first_name} {internship.student.last_name}".strip()


def _is_approved_internship(internship: Internship) -> bool:
    return internship.status is not None and internship.status.title == APPROVED_INTERNSHIP_STATUS


class SupervisorEvaluationService:
    """Orquesta invitaciones, consulta publica y envio de evaluaciones."""

    def __init__(
        self,
        repository: SupervisorEvaluationRepository,
        notification_service: NotificationService | None = None,
        app_config: type | object = config,
    ) -> None:
        self.repository = repository
        self.notification_service = notification_service
        self.app_config = app_config

    async def generate_invitation(
        self,
        *,
        internship_id: int,
        actor: User,
    ) -> SupervisorEvaluationInvitationResponse:
        """Genera o reenvia una invitacion de evaluacion para una practica."""

        return await self.generate_invitation_for_internship(
            internship_id=internship_id,
            created_by_user_id=actor.id,
        )

    async def generate_invitation_for_internship(
        self,
        *,
        internship_id: int,
        created_by_user_id: int | None = None,
    ) -> SupervisorEvaluationInvitationResponse:
        """Genera una invitacion cuando la autoevaluacion ya fue enviada."""

        internship = await self.repository.get_internship(internship_id)
        if internship is None:
            raise SupervisorEvaluationError(404, "Internship not found")
        if internship.is_cancelled:
            raise SupervisorEvaluationError(409, "Internship is cancelled")
        if not _is_approved_internship(internship):
            raise SupervisorEvaluationError(409, "Internship is not approved")
        if not await self.repository.has_submitted_self_evaluation(internship_id):
            raise SupervisorEvaluationError(
                409,
                "La autoevaluación del estudiante aún no ha sido enviada",
            )

        existing_evaluation = await self.repository.get_evaluation_by_internship(
            internship_id
        )
        if existing_evaluation is not None:
            raise SupervisorEvaluationError(409, "Supervisor evaluation already submitted")

        revoked_count = await self.repository.revoke_active_invitations(internship_id)
        token = secrets.token_urlsafe(32)
        invitation = SupervisorEvaluationInvitation(
            internship_id=internship.id,
            supervisor_name_snapshot=internship.supervisor_name,
            supervisor_email_snapshot=internship.supervisor_email,
            token_hash=_hash_token(token),
            expires_at=_utc_now() + timedelta(days=INVITATION_TTL_DAYS),
            sent_at=_utc_now(),
            created_by=created_by_user_id,
        )
        invitation = await self.repository.create_invitation(invitation)

        public_url = self._build_public_url(token)
        await self._dispatch_invitation_notification(
            internship=internship,
            invitation_url=public_url,
        )

        demo_token = token if self._is_simulated_mode() else None
        return SupervisorEvaluationInvitationResponse(
            invitation_id=invitation.id,
            internship_id=internship.id,
            supervisor_email=internship.supervisor_email,
            expires_at=invitation.expires_at,
            revoked_previous_count=revoked_count,
            demo_token=demo_token,
            demo_url=public_url if demo_token else None,
        )

    async def get_public_evaluation_form(
        self,
        token: str,
    ) -> SupervisorEvaluationPublicResponse:
        """Retorna informacion minima de una invitacion publica valida."""

        invitation = await self._get_valid_invitation(token)
        internship = invitation.internship

        return SupervisorEvaluationPublicResponse(
            internship_id=internship.id,
            org_name=internship.org_name,
            student_name=_student_name(internship),
            internship_type=internship.internship_type.value,
            start_date=internship.start_date,
            end_date=internship.end_date,
            supervisor_name=invitation.supervisor_name_snapshot,
            criteria=self._criteria_response(),
        )

    async def submit_public_evaluation(
        self,
        *,
        token: str,
        payload: SupervisorEvaluationSubmitRequest,
    ) -> SupervisorEvaluationSubmitResponse:
        """Persiste una evaluacion publica y consume la invitacion."""

        invitation = await self._get_valid_invitation(token)
        existing_evaluation = await self.repository.get_evaluation_by_internship(
            invitation.internship_id
        )
        if existing_evaluation is not None:
            raise SupervisorEvaluationError(409, "Supervisor evaluation already submitted")

        evaluation = SupervisorEvaluation(
            internship_id=invitation.internship_id,
            invitation_id=invitation.id,
            supervisor_name_snapshot=invitation.supervisor_name_snapshot,
            supervisor_email_snapshot=invitation.supervisor_email_snapshot,
            criteria_scores=payload.criteria_scores,
            observations=payload.observations,
            recommendation=payload.recommendation,
            status="submitted",
        )
        internship = invitation.internship
        if (
            internship is not None
            and internship.status is not None
            and internship.status.title == "Aprobada"
            and internship.completion_status != CompletionStatusEnum.finalized
            and internship.end_date <= _utc_now().date()
        ):
            internship.completion_status = CompletionStatusEnum.pending_presentation

        evaluation = await self.repository.create_evaluation_and_mark_invitation_used(
            evaluation=evaluation,
            invitation=invitation,
        )

        return SupervisorEvaluationSubmitResponse(
            evaluation_id=evaluation.id,
            internship_id=evaluation.internship_id,
            submitted_at=evaluation.submitted_at,
        )

    async def get_evaluation_for_user(
        self,
        *,
        internship_id: int,
        actor: User,
    ) -> SupervisorEvaluation:
        """Obtiene la evaluacion si el actor es propietario, Encargado o Director."""

        internship = await self.repository.get_internship(internship_id)
        if internship is None:
            raise SupervisorEvaluationError(404, "Internship not found")
        if not self._can_read_evaluation(actor=actor, internship=internship):
            raise SupervisorEvaluationError(403, "Insufficient permissions")

        evaluation = await self.repository.get_evaluation_by_internship(internship_id)
        if evaluation is None:
            raise SupervisorEvaluationError(404, "Supervisor evaluation not found")

        return evaluation

    async def list_assignments_for_supervisor(
        self,
        actor: User,
    ) -> list[SupervisorAssignmentResponse]:
        """Lista practicas asignadas al supervisor autenticado por correo."""

        if SUPERVISOR_ROLE not in _role_names(actor):
            raise SupervisorEvaluationError(403, "Insufficient permissions")

        internships = await self.repository.list_internships_by_supervisor_email(
            actor.email
        )
        assignments = []
        for internship in internships:
            evaluation = await self.repository.get_evaluation_by_internship(internship.id)
            assignments.append(
                SupervisorAssignmentResponse(
                    internship_id=internship.id,
                    org_name=internship.org_name,
                    student_name=_student_name(internship),
                    internship_type=internship.internship_type.value,
                    start_date=internship.start_date,
                    end_date=internship.end_date,
                    status_label=internship.status.title if internship.status else "Pendiente",
                    evaluation_submitted=evaluation is not None,
                )
            )

        return assignments

    async def _get_valid_invitation(
        self,
        token: str,
    ) -> SupervisorEvaluationInvitation:
        invitation = await self.repository.get_invitation_by_token_hash(_hash_token(token))
        if invitation is None:
            raise SupervisorEvaluationError(404, "Supervisor invitation not found")
        if invitation.revoked_at is not None:
            raise SupervisorEvaluationError(409, "Supervisor invitation revoked")
        if invitation.used_at is not None:
            raise SupervisorEvaluationError(409, "Supervisor invitation already used")
        if invitation.expires_at <= _utc_now():
            raise SupervisorEvaluationError(410, "Supervisor invitation expired")
        if invitation.internship is None or invitation.internship.is_cancelled:
            raise SupervisorEvaluationError(409, "Internship is not available")
        if not _is_approved_internship(invitation.internship):
            raise SupervisorEvaluationError(409, "Internship is not approved")

        return invitation

    def _can_read_evaluation(self, *, actor: User, internship: Internship) -> bool:
        if internship.user_id == actor.id:
            return True
        return bool(_role_names(actor) & ADMIN_ROLES)

    def _build_public_url(self, token: str) -> str:
        origins = getattr(self.app_config, "CORS_ALLOWED_ORIGINS", [])
        base_url = origins[0] if origins else "http://localhost:5173"
        return f"{base_url.rstrip('/')}/supervisor/evaluacion/{token}"

    def _is_simulated_mode(self) -> bool:
        return getattr(self.app_config, "NOTIFICATION_MODE", "simulated") == "simulated"

    def _criteria_response(self) -> list[SupervisorEvaluationCriteriaResponse]:
        return [
            SupervisorEvaluationCriteriaResponse(**criterion)
            for criterion in SUPERVISOR_EVALUATION_CRITERIA
        ]

    async def _dispatch_invitation_notification(
        self,
        *,
        internship: Internship,
        invitation_url: str,
    ) -> None:
        if self.notification_service is None:
            return

        notification = Notification(
            recipient_user_id=None,
            recipient_email=internship.supervisor_email,
            event_type=NotificationEventTypeEnum.custom,
            subject="Evaluación de práctica pendiente",
            content=(
                "Tiene una evaluación de práctica pendiente en la plataforma. "
                f"Ingrese al formulario desde este enlace: {invitation_url}"
            ),
            status=NotificationStatusEnum.simulated,
            payload={"internship_id": internship.id, "event": "supervisor_evaluation_invitation"},
        )
        await self.notification_service.create_and_dispatch(notification)
