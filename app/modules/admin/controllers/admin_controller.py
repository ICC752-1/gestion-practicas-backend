"""Controlador HTTP del modulo admin.

Este modulo define las rutas administrativas de solo lectura orientadas al rol
`Encargado de practica`.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.database import get_db
from app.modules.admin.schemas.admin_schema import (
    AdminInternshipDetailResponse,
    AdminInternshipListItem,
    AdminStudentListItem,
    AdminSummaryResponse,
)
from app.modules.admin.services.admin_service import AdminService
from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.auth.models.user_model import User


router = APIRouter(prefix="/admin", tags=["Admin"])
logger = logging.getLogger(__name__)

PRACTICE_MANAGER_ROLE = "Encargado de practica"


def _build_service(db: AsyncSession) -> AdminService:
    """Construye el servicio administrativo para un request.

    Args:
        db: Sesion asincrona de SQLAlchemy inyectada por FastAPI.

    Returns:
        Instancia de `AdminService` configurada para el request actual.
    """

    return AdminService(db)


@router.get("/summary", response_model=AdminSummaryResponse)
async def get_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([PRACTICE_MANAGER_ROLE]))],
) -> AdminSummaryResponse:
    """Obtiene el resumen administrativo visible para el encargado.

    Args:
        db            : Sesion asincrona de base de datos inyectada por `get_db`.
        current_user  : Usuario autenticado validado por `require_roles`.

    Returns:
        `AdminSummaryResponse` con totales globales y practicas por estado.
    """

    logger.info("Admin summary request received", extra={"user_id": current_user.id})

    service = _build_service(db)

    return await service.get_summary()


@router.get("/students", response_model=list[AdminStudentListItem])
async def get_students(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([PRACTICE_MANAGER_ROLE]))],
) -> list[AdminStudentListItem]:
    """Obtiene el listado administrativo de estudiantes.

    Args:
        db            : Sesion asincrona de base de datos inyectada por `get_db`.
        current_user  : Usuario autenticado validado por `require_roles`.

    Returns:
        Lista de estudiantes visible para el encargado de practica.
    """

    logger.info("Admin students request received", extra={"user_id": current_user.id})

    service = _build_service(db)

    return await service.get_students()


@router.get("/internships", response_model=list[AdminInternshipListItem])
async def get_internships(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([PRACTICE_MANAGER_ROLE]))],
) -> list[AdminInternshipListItem]:
    """Obtiene el listado administrativo de practicas.

    Args:
        db            : Sesion asincrona de base de datos inyectada por `get_db`.
        current_user  : Usuario autenticado validado por `require_roles`.

    Returns:
        Lista de practicas visible para el encargado de practica.
    """

    logger.info(
        "Admin internships request received",
        extra={"user_id": current_user.id},
    )

    service = _build_service(db)

    return await service.get_internships()


@router.get(
    "/internships/{internship_id}", response_model=AdminInternshipDetailResponse
)
async def get_internship_detail(
    internship_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles([PRACTICE_MANAGER_ROLE]))],
) -> AdminInternshipDetailResponse:
    """Obtiene el detalle administrativo de una practica.

    Args:
        internship_id  : Identificador entero de la practica solicitada.
        db             : Sesion asincrona de base de datos inyectada por `get_db`.
        current_user   : Usuario autenticado validado por `require_roles`.

    Returns:
        `AdminInternshipDetailResponse` con el detalle de la practica.

    Raises:
        HTTPException: Con codigo 404 si la practica no existe.
    """

    logger.info(
        "Admin internship detail request received",
        extra={"user_id": current_user.id, "internship_id": internship_id},
    )

    service = _build_service(db)
    internship = await service.get_internship_detail(internship_id)

    if internship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Internship not found",
        )

    return internship
