"""Controlador HTTP para administracion de contenido de induccion."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.database import get_db
from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.auth.models.user_model import User
from app.modules.auth.utils.roles import CAREER_DIRECTOR_ROLE, PRACTICE_MANAGER_ROLE
from app.modules.internships.repositories.internship_repository import InternshipRepository
from app.modules.internships.schemas.induction_admin_schema import (
    InductionAdminVersionDetailResponse,
    InductionAdminVersionPayload,
    InductionAdminVersionSummaryResponse,
)
from app.modules.internships.services.induction_admin_service import (
    InductionAdminService,
)

router = APIRouter(prefix="/induction/admin", tags=["Induction admin"])
INDUCTION_ADMIN_ROLES = [PRACTICE_MANAGER_ROLE, CAREER_DIRECTOR_ROLE]


def _build_service(db: AsyncSession) -> InductionAdminService:
    return InductionAdminService(repository=InternshipRepository(db))


@router.get("/versions", response_model=list[InductionAdminVersionSummaryResponse])
async def list_induction_versions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(INDUCTION_ADMIN_ROLES))],
) -> list[InductionAdminVersionSummaryResponse]:
    """Lista el historial de versiones de induccion para administracion."""

    service = _build_service(db)
    versions = await service.list_versions()

    return [
        InductionAdminVersionSummaryResponse.model_validate(version)
        for version in versions
    ]


@router.post(
    "/versions",
    response_model=InductionAdminVersionDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_induction_draft(
    payload: InductionAdminVersionPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(INDUCTION_ADMIN_ROLES))],
) -> InductionAdminVersionDetailResponse:
    """Crea una version borrador de induccion."""

    service = _build_service(db)
    version = await service.create_draft(payload)

    return InductionAdminVersionDetailResponse.model_validate(version)


@router.get(
    "/versions/{version_id}",
    response_model=InductionAdminVersionDetailResponse,
)
async def get_induction_version(
    version_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(INDUCTION_ADMIN_ROLES))],
) -> InductionAdminVersionDetailResponse:
    """Obtiene detalle administrativo, incluida respuesta correcta."""

    service = _build_service(db)
    version = await service.get_version(version_id)

    return InductionAdminVersionDetailResponse.model_validate(version)


@router.patch(
    "/versions/{version_id}",
    response_model=InductionAdminVersionDetailResponse,
)
async def update_induction_draft(
    version_id: int,
    payload: InductionAdminVersionPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(INDUCTION_ADMIN_ROLES))],
) -> InductionAdminVersionDetailResponse:
    """Edita una version mientras sigue en borrador."""

    service = _build_service(db)
    version = await service.update_draft(version_id, payload)

    return InductionAdminVersionDetailResponse.model_validate(version)


@router.delete("/versions/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
async def discard_induction_draft(
    version_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(INDUCTION_ADMIN_ROLES))],
) -> None:
    """Descarta una version en borrador."""

    service = _build_service(db)
    await service.discard_draft(version_id)

    return None


@router.post(
    "/versions/{version_id}/publish",
    response_model=InductionAdminVersionDetailResponse,
)
async def publish_induction_version(
    version_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(INDUCTION_ADMIN_ROLES))],
) -> InductionAdminVersionDetailResponse:
    """Publica una version y la deja como unica activa."""

    service = _build_service(db)
    version = await service.publish(version_id)

    return InductionAdminVersionDetailResponse.model_validate(version)
