"""Rutas HTTP para autoevaluaciones de estudiantes."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import config
from app.core.database.database import get_db
from app.modules.auth.dependencies.auth_dependency import get_current_user
from app.modules.auth.models.user_model import User
from app.modules.notifications.repositories.notification_repository import (
    NotificationRepository,
)
from app.modules.notifications.services.notification_service import NotificationService
from app.modules.self_evaluations.repositories.self_evaluation_repository import (
    SelfEvaluationRepository,
)
from app.modules.self_evaluations.schemas.self_evaluation_schema import (
    SelfEvaluationDraftRequest,
    SelfEvaluationFormResponse,
    SelfEvaluationReopenRequest,
    SelfEvaluationResponse,
    SelfEvaluationSubmitRequest,
)
from app.modules.self_evaluations.services.self_evaluation_service import (
    SelfEvaluationService,
)

router = APIRouter(prefix="/self-evaluations", tags=["Self evaluations"])


def _build_service(db: AsyncSession) -> SelfEvaluationService:
    notification_service = NotificationService(
        notification_repository=NotificationRepository(db),
        app_config=config,
    )
    return SelfEvaluationService(
        repository=SelfEvaluationRepository(db),
        notification_service=notification_service,
    )


@router.get(
    "/internships/{internship_id}/form",
    response_model=SelfEvaluationFormResponse,
)
async def get_self_evaluation_form(
    internship_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SelfEvaluationFormResponse:
    service = _build_service(db)
    return await service.get_form(internship_id=internship_id, actor=current_user)


@router.get("/me", response_model=list[SelfEvaluationResponse])
async def list_my_self_evaluations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[SelfEvaluationResponse]:
    service = _build_service(db)
    evaluations = await service.list_my_evaluations(actor=current_user)
    return [SelfEvaluationResponse.model_validate(item) for item in evaluations]


@router.put(
    "/internships/{internship_id}/draft",
    response_model=SelfEvaluationResponse,
)
async def save_self_evaluation_draft(
    internship_id: int,
    payload: SelfEvaluationDraftRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SelfEvaluationResponse:
    service = _build_service(db)
    evaluation = await service.save_draft(
        internship_id=internship_id,
        payload=payload,
        actor=current_user,
    )
    return SelfEvaluationResponse.model_validate(evaluation)


@router.post(
    "/internships/{internship_id}/submit",
    response_model=SelfEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_self_evaluation(
    internship_id: int,
    payload: SelfEvaluationSubmitRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SelfEvaluationResponse:
    service = _build_service(db)
    evaluation = await service.submit(
        internship_id=internship_id,
        payload=payload,
        actor=current_user,
    )
    return SelfEvaluationResponse.model_validate(evaluation)


@router.post(
    "/{evaluation_id}/reopen",
    response_model=SelfEvaluationResponse,
)
async def reopen_self_evaluation(
    evaluation_id: int,
    payload: SelfEvaluationReopenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SelfEvaluationResponse:
    service = _build_service(db)
    evaluation = await service.reopen(
        evaluation_id=evaluation_id,
        payload=payload,
        actor=current_user,
    )
    return SelfEvaluationResponse.model_validate(evaluation)
