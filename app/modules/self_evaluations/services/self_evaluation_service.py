"""Casos de uso de autoevaluaciones de estudiantes."""

import logging
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException, status

from app.modules.auth.models.user_model import User
from app.modules.internships.models.internship_model import CompletionStatusEnum, Internship
from app.modules.notifications.models.notification_model import (
    Notification,
    NotificationEventTypeEnum,
    NotificationStatusEnum,
)
from app.modules.notifications.services.notification_service import NotificationService
from app.modules.self_evaluations.models.self_evaluation_model import (
    SelfEvaluation,
    SelfEvaluationStatusEnum,
)
from app.modules.self_evaluations.repositories.self_evaluation_repository import (
    SelfEvaluationRepository,
)
from app.modules.self_evaluations.schemas.self_evaluation_schema import (
    SELF_EVALUATION_CRITERIA,
    SELF_EVALUATION_FORM_VERSION,
    SELF_EVALUATION_SCALE,
    SelfEvaluationDraftRequest,
    SelfEvaluationFormResponse,
    SelfEvaluationInternshipSummary,
    SelfEvaluationReopenRequest,
    SelfEvaluationResponse,
    SelfEvaluationScaleResponse,
    SelfEvaluationSubmitRequest,
)
from app.modules.supervisor_evaluations.services.supervisor_evaluation_service import (
    SupervisorEvaluationError,
    SupervisorEvaluationService,
)

logger = logging.getLogger(__name__)

STUDENT_ROLE = "Estudiante"
ADMIN_ROLES = {"Encargado de practica", "Director de carrera", "Secretaria de Carrera"}
ENABLED_COMPLETION_STATUSES = {
    CompletionStatusEnum.pending_evaluations,
    CompletionStatusEnum.pending_presentation,
    CompletionStatusEnum.finalized,
}
SELF_EVALUATION_BUSINESS_DAYS_BEFORE_END = 5


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _role_names(user: User) -> set[str]:
    return {user_role.role.name for user_role in user.roles}


class SelfEvaluationService:
    """Orquesta formulario, borrador, envio y reapertura auditada."""

    def __init__(
        self,
        repository: SelfEvaluationRepository,
        notification_service: NotificationService | None = None,
        supervisor_evaluation_service: SupervisorEvaluationService | None = None,
    ) -> None:
        self.repository = repository
        self.notification_service = notification_service
        self.supervisor_evaluation_service = supervisor_evaluation_service

    async def get_form(
        self,
        *,
        internship_id: int,
        actor: User,
    ) -> SelfEvaluationFormResponse:
        internship = await self._get_owned_internship(internship_id, actor)
        evaluation = await self.repository.get_by_internship(internship.id)
        enabled, reason = self._is_enabled(internship)

        status_label = "not_started"
        if not enabled:
            status_label = "not_enabled"
        if evaluation is not None:
            status_label = evaluation.status.value

        return SelfEvaluationFormResponse(
            internship=self._internship_summary(internship),
            form_version=SELF_EVALUATION_FORM_VERSION,
            scale=SelfEvaluationScaleResponse(**SELF_EVALUATION_SCALE),
            criteria=SELF_EVALUATION_CRITERIA,
            enabled=enabled,
            status=status_label,
            reason=reason,
            evaluation=(
                SelfEvaluationResponse.model_validate(evaluation)
                if evaluation is not None
                else None
            ),
        )

    async def save_draft(
        self,
        *,
        internship_id: int,
        payload: SelfEvaluationDraftRequest,
        actor: User,
    ) -> SelfEvaluation:
        internship = await self._get_owned_internship(internship_id, actor)
        self._require_enabled(internship)

        evaluation = await self.repository.get_by_internship(internship.id)
        if evaluation is None:
            evaluation = SelfEvaluation(
                internship_id=internship.id,
                student_id=actor.id,
                form_version=SELF_EVALUATION_FORM_VERSION,
                criteria_snapshot=SELF_EVALUATION_CRITERIA,
                responses={},
                status=SelfEvaluationStatusEnum.draft,
            )
        else:
            self._check_concurrency(evaluation, payload.expected_updated_at)
            if evaluation.status == SelfEvaluationStatusEnum.submitted:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="La autoevaluación enviada no puede editarse sin reapertura",
                )

        evaluation.responses = payload.responses
        evaluation.observations = _clean_text(payload.observations)
        if evaluation.status == SelfEvaluationStatusEnum.reopened:
            evaluation.status = SelfEvaluationStatusEnum.draft

        return await self.repository.save(evaluation)

    async def submit(
        self,
        *,
        internship_id: int,
        payload: SelfEvaluationSubmitRequest,
        actor: User,
    ) -> SelfEvaluation:
        internship = await self._get_owned_internship(internship_id, actor)
        self._require_enabled(internship)

        evaluation = await self.repository.get_by_internship(internship.id)
        if evaluation is not None:
            self._check_concurrency(evaluation, payload.expected_updated_at)
            if evaluation.status == SelfEvaluationStatusEnum.submitted:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="La autoevaluación ya fue enviada",
                )
        else:
            evaluation = SelfEvaluation(
                internship_id=internship.id,
                student_id=actor.id,
                form_version=SELF_EVALUATION_FORM_VERSION,
                criteria_snapshot=SELF_EVALUATION_CRITERIA,
            )

        now = _utc_now()
        evaluation.responses = payload.responses
        evaluation.observations = _clean_text(payload.observations)
        evaluation.status = SelfEvaluationStatusEnum.submitted
        evaluation.submitted_at = now

        saved = await self.repository.save(evaluation)
        await self._notify_submission(internship=internship, evaluation=saved)
        await self._generate_supervisor_invitation_after_submission(internship)
        return saved

    async def reopen(
        self,
        *,
        evaluation_id: int,
        payload: SelfEvaluationReopenRequest,
        actor: User,
    ) -> SelfEvaluation:
        if not (_role_names(actor) & ADMIN_ROLES):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para reabrir autoevaluaciones",
            )

        evaluation = await self.repository.get_by_id(evaluation_id)
        if evaluation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Autoevaluación no encontrada",
            )
        if evaluation.status != SelfEvaluationStatusEnum.submitted:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Solo se puede reabrir una autoevaluación enviada",
            )

        evaluation.status = SelfEvaluationStatusEnum.reopened
        evaluation.reopened_at = _utc_now()
        evaluation.reopened_by = actor.id
        evaluation.reopen_reason = payload.reason.strip()
        return await self.repository.save(evaluation)

    async def list_my_evaluations(self, *, actor: User) -> list[SelfEvaluation]:
        if STUDENT_ROLE not in _role_names(actor):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo estudiantes pueden listar sus autoevaluaciones",
            )
        return await self.repository.list_by_student(actor.id)

    async def _get_owned_internship(self, internship_id: int, actor: User) -> Internship:
        if STUDENT_ROLE not in _role_names(actor):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo estudiantes pueden completar autoevaluaciones",
            )

        internship = await self.repository.get_internship(internship_id)
        if internship is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Práctica no encontrada",
            )
        if internship.user_id != actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No puedes acceder a la autoevaluación de otra práctica",
            )
        return internship

    def _require_enabled(self, internship: Internship) -> None:
        enabled, reason = self._is_enabled(internship)
        if not enabled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "La autoevaluación aún no está habilitada",
                    "reason": reason,
                },
            )

    @staticmethod
    def _is_enabled(
        internship: Internship,
        *,
        today: date | None = None,
    ) -> tuple[bool, str | None]:
        if internship.is_cancelled:
            return False, "La práctica está anulada"
        if internship.status is not None and internship.status.title != "Aprobada":
            return False, "La práctica debe estar aprobada administrativamente"

        current_date = today or _utc_now().date()
        business_window_start = _business_window_start(
            internship.end_date,
            SELF_EVALUATION_BUSINESS_DAYS_BEFORE_END,
        )
        if current_date >= business_window_start:
            return True, None

        completion_status = getattr(
            internship.completion_status,
            "value",
            internship.completion_status,
        )
        enabled_statuses = {item.value for item in ENABLED_COMPLETION_STATUSES}
        if completion_status not in enabled_statuses:
            return (
                False,
                "La autoevaluación se habilita desde los últimos 5 días hábiles de la práctica",
            )
        return True, None

    @staticmethod
    def _check_concurrency(
        evaluation: SelfEvaluation,
        expected_updated_at: datetime | None,
    ) -> None:
        if expected_updated_at is None:
            return
        if evaluation.updated_at.replace(tzinfo=None) != expected_updated_at.replace(
            tzinfo=None
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La autoevaluación fue modificada en otra sesión",
            )

    @staticmethod
    def _internship_summary(internship: Internship) -> SelfEvaluationInternshipSummary:
        return SelfEvaluationInternshipSummary(
            id=internship.id,
            org_name=internship.org_name,
            internship_type=getattr(
                internship.internship_type,
                "value",
                internship.internship_type,
            ),
            start_date=internship.start_date,
            end_date=internship.end_date,
            completion_status=getattr(
                internship.completion_status,
                "value",
                internship.completion_status,
            ),
            final_result=getattr(
                internship.final_result,
                "value",
                internship.final_result,
            ),
        )

    async def _notify_submission(
        self,
        *,
        internship: Internship,
        evaluation: SelfEvaluation,
    ) -> None:
        if self.notification_service is None:
            return

        notification = Notification(
            recipient_user_id=internship.user_id,
            recipient_email=internship.student.email if internship.student else None,
            event_type=NotificationEventTypeEnum.custom,
            subject="Autoevaluación enviada",
            content="Tu autoevaluación de práctica fue registrada correctamente.",
            status=NotificationStatusEnum.simulated,
            payload={
                "event": "self_evaluation_submitted",
                "internship_id": internship.id,
                "self_evaluation_id": evaluation.id,
            },
        )
        await self.notification_service.create_and_dispatch(notification)

        recipients = await self.repository.list_users_by_roles(ADMIN_ROLES)
        for recipient in recipients:
            admin_notification = Notification(
                recipient_user_id=recipient.id,
                recipient_email=recipient.email,
                event_type=NotificationEventTypeEnum.custom,
                subject="Autoevaluación de estudiante enviada",
                content=(
                    "Un estudiante envió su autoevaluación de práctica. "
                    f"Práctica #{internship.id}."
                ),
                status=NotificationStatusEnum.simulated,
                payload={
                    "event": "self_evaluation_submitted_admin",
                    "internship_id": internship.id,
                    "self_evaluation_id": evaluation.id,
                    "student_id": internship.user_id,
                },
            )
            await self.notification_service.create_and_dispatch(admin_notification)

    async def _generate_supervisor_invitation_after_submission(
        self,
        internship: Internship,
    ) -> None:
        """Genera el link del supervisor sin bloquear el envío de autoevaluación."""

        if self.supervisor_evaluation_service is None:
            return

        try:
            await self.supervisor_evaluation_service.generate_invitation_for_internship(
                internship_id=internship.id,
                created_by_user_id=None,
            )
        except SupervisorEvaluationError:
            logger.warning(
                "No se pudo generar invitación automática de supervisor para "
                "práctica ID: %s tras autoevaluación.",
                internship.id,
                exc_info=True,
            )
        except Exception:
            logger.warning(
                "Fallo inesperado al generar invitación automática de supervisor "
                "para práctica ID: %s.",
                internship.id,
                exc_info=True,
            )


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _business_window_start(end_date: date, business_days: int) -> date:
    cursor = end_date
    remaining = business_days

    while remaining > 0:
        if cursor.weekday() < 5:
            remaining -= 1
            if remaining == 0:
                return cursor
        cursor -= timedelta(days=1)

    return end_date
