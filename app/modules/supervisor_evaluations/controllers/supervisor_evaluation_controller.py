"""Controlador HTTP para invitaciones y evaluaciones de supervisores."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import config
from app.core.database.database import get_db
from app.modules.auth.dependencies.auth_dependency import get_current_user
from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.auth.models.user_model import User
from app.modules.notifications.repositories.notification_repository import (
    NotificationRepository,
)
from app.modules.notifications.services.notification_service import NotificationService
from app.modules.supervisor_evaluations.repositories.supervisor_evaluation_repository import (
    SupervisorEvaluationRepository,
)
from app.modules.supervisor_evaluations.schemas.supervisor_evaluation_schema import (
    SupervisorAssignmentResponse,
    SupervisorEvaluationAdminResponse,
    SupervisorEvaluationInvitationResponse,
    SupervisorEvaluationPublicResponse,
    SupervisorEvaluationSubmitRequest,
    SupervisorEvaluationSubmitResponse,
)
from app.modules.supervisor_evaluations.services.supervisor_evaluation_service import (
    ADMIN_ROLES,
    SupervisorEvaluationError,
    SupervisorEvaluationService,
)

router = APIRouter(prefix="/supervisor/evaluations", tags=["Supervisor evaluations"])


def _build_service(db: AsyncSession) -> SupervisorEvaluationService:
    notification_service = NotificationService(
        notification_repository=NotificationRepository(db),
        app_config=config,
    )
    return SupervisorEvaluationService(
        repository=SupervisorEvaluationRepository(db),
        notification_service=notification_service,
        app_config=config,
    )


def _raise_http_error(error: SupervisorEvaluationError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.post(
    "/internships/{internship_id}/invitations",
    response_model=SupervisorEvaluationInvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_supervisor_invitation(
    internship_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(list(ADMIN_ROLES)))],
) -> SupervisorEvaluationInvitationResponse:
    """Genera o reenvia una invitacion de evaluacion para una practica."""

    service = _build_service(db)
    try:
        return await service.generate_invitation(
            internship_id=internship_id,
            actor=current_user,
        )
    except SupervisorEvaluationError as error:
        _raise_http_error(error)


@router.get(
    "/invitations/{token}",
    response_model=SupervisorEvaluationPublicResponse,
)
async def get_public_supervisor_evaluation_form(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SupervisorEvaluationPublicResponse:
    """Consulta publica minima para renderizar el formulario por token."""

    service = _build_service(db)
    try:
        return await service.get_public_evaluation_form(token)
    except SupervisorEvaluationError as error:
        _raise_http_error(error)


@router.post(
    "/invitations/{token}/submit",
    response_model=SupervisorEvaluationSubmitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_public_supervisor_evaluation(
    token: str,
    payload: SupervisorEvaluationSubmitRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SupervisorEvaluationSubmitResponse:
    """Envia una evaluacion publica y consume el token en una sola transaccion."""

    service = _build_service(db)
    try:
        return await service.submit_public_evaluation(token=token, payload=payload)
    except SupervisorEvaluationError as error:
        _raise_http_error(error)


@router.get(
    "/internships/{internship_id}",
    response_model=SupervisorEvaluationAdminResponse,
)
async def get_supervisor_evaluation_for_internship(
    internship_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SupervisorEvaluationAdminResponse:
    """Consulta la evaluacion para estudiante propietario, Encargado o Director."""

    service = _build_service(db)
    try:
        evaluation = await service.get_evaluation_for_user(
            internship_id=internship_id,
            actor=current_user,
        )
    except SupervisorEvaluationError as error:
        _raise_http_error(error)

    return SupervisorEvaluationAdminResponse.model_validate(evaluation)


@router.get("/me", response_model=list[SupervisorAssignmentResponse])
async def list_my_supervisor_assignments(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[SupervisorAssignmentResponse]:
    """Lista practicas visibles para un usuario con rol Supervisor de practica."""

    service = _build_service(db)
    try:
        return await service.list_assignments_for_supervisor(actor=current_user)
    except SupervisorEvaluationError as error:
        _raise_http_error(error)
