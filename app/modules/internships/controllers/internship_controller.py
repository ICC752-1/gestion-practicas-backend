"""HTTP controller for internship endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.database import get_db
from app.modules.auth.dependencies.auth_dependency import get_current_user
from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.auth.models.user_model import User
from app.modules.internships.models.internship_model import Internship
from app.modules.internships.repositories.internship_repository import (
    InternshipRepository,
)
from app.modules.internships.schemas.internship_schema import (
    InternshipCreateRequest,
    InternshipResponse,
)
from app.modules.internships.services.internship_service import InternshipService

router = APIRouter(prefix="/internships", tags=["Internships"])

STUDENT_ROLE = "Estudiante"
PRIVILEGED_READ_ROLES = {
    "Encargado de practica",
    "Director de carrera",
    "Secretaria de Carrera",
}


def _has_any_role(user: User, role_names: set[str]) -> bool:
    return any(user_role.role.name in role_names for user_role in user.roles)


def _can_read_internship(user: User, internship: Internship) -> bool:
    return internship.user_id == user.id or _has_any_role(user, PRIVILEGED_READ_ROLES)


def _build_service(db: AsyncSession) -> InternshipService:
    return InternshipService(
        internship_repository=InternshipRepository(db),
    )


@router.post(
    "",
    response_model=InternshipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_internship(
    internship_data: InternshipCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([STUDENT_ROLE]))],
) -> InternshipResponse:
    service = _build_service(db)
    internship = await service.create_internship(
        internship_data=internship_data,
        user_id=current_user.id,
    )

    return InternshipResponse.model_validate(internship)


@router.get("/me", response_model=list[InternshipResponse])
async def list_my_internships(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[InternshipResponse]:
    service = _build_service(db)
    internships = await service.list_user_internships(user_id=current_user.id)

    return [
        InternshipResponse.model_validate(internship)
        for internship in internships
    ]


@router.get("/{internship_id}", response_model=InternshipResponse)
async def get_internship(
    internship_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> InternshipResponse:
    service = _build_service(db)
    internship = await service.get_internship(internship_id=internship_id)

    if internship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Internship not found",
        )

    if not _can_read_internship(user=current_user, internship=internship):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    return InternshipResponse.model_validate(internship)
