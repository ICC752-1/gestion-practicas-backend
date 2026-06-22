"""Controlador HTTP del modulo admin.

Este modulo define rutas administrativas de consulta y gestion de requisitos.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.database import get_db
from app.core.config import config
from app.modules.admin.schemas.admin_schema import (
    AdminInternshipStatusFilter,
    AdminInternshipDetailResponse,
    AdminInternshipListItem,
    AdminRegistrationRequirementItem,
    AdminStudentInternshipRequirementItem,
    AdminStudentListItem,
    AdminSummaryResponse,
    AdminUpdateInternshipSchoolInsuranceRequest,
    AdminUpdateSchoolInsuranceRequest,
    AdminUpdateStudentInternshipRequirementStatusRequest,
)
from app.modules.admin.services.admin_service import AdminService
from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.auth.models.user_model import User
from app.modules.auth.utils.roles import (
    CAREER_DIRECTOR_ROLE,
    PRACTICE_MANAGER_ROLE,
)
from app.modules.notifications.repositories.notification_repository import (
    NotificationRepository,
)
from app.modules.notifications.services.notification_service import (
    NotificationService,
)


router = APIRouter(prefix="/admin", tags=["Admin"])
logger = logging.getLogger(__name__)

ADMIN_READ_ROLES = [
    PRACTICE_MANAGER_ROLE,
    CAREER_DIRECTOR_ROLE,
]
SCHOOL_INSURANCE_ADMIN_ROLES = [
    CAREER_DIRECTOR_ROLE,
]


def _build_service(db: AsyncSession) -> AdminService:
    """Construye el servicio administrativo para un request.

    Args:
        db: Sesion asincrona de SQLAlchemy inyectada por FastAPI.

    Returns:
        Instancia de `AdminService` configurada para el request actual.
    """

    notification_service = NotificationService(
        notification_repository=NotificationRepository(db),
        app_config=config,
    )

    return AdminService(db, notification_service=notification_service)


@router.get("/summary", response_model=AdminSummaryResponse)
async def get_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(ADMIN_READ_ROLES))],
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
    current_user: Annotated[User, Depends(require_roles(ADMIN_READ_ROLES))],
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
    current_user: Annotated[User, Depends(require_roles(ADMIN_READ_ROLES))],
    status_filter: Annotated[
        AdminInternshipStatusFilter | None,
        Query(alias="status"),
    ] = None,
) -> list[AdminInternshipListItem]:
    """Obtiene el listado administrativo de practicas.

    Args:
        db            : Sesion asincrona de base de datos inyectada por `get_db`.
        current_user  : Usuario autenticado validado por `require_roles`.
        status_filter : Estado normalizado opcional para dashboard.

    Returns:
        Lista de practicas visible para el encargado de practica.
    """

    logger.info(
        "Admin internships request received",
        extra={"user_id": current_user.id},
    )

    service = _build_service(db)

    return await service.get_internships(status_filter=status_filter)


@router.get(
    "/internships/{internship_id}", response_model=AdminInternshipDetailResponse
)
async def get_internship_detail(
    internship_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(ADMIN_READ_ROLES))],
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


@router.patch(
    "/internships/{internship_id}/school-insurance",
    response_model=AdminInternshipDetailResponse,
)
async def update_internship_school_insurance(
    internship_id: int,
    payload: AdminUpdateInternshipSchoolInsuranceRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_roles(SCHOOL_INSURANCE_ADMIN_ROLES)),
    ],
) -> AdminInternshipDetailResponse:
    """Actualiza la validacion de seguro escolar de una solicitud concreta."""

    logger.info(
        "Admin internship school insurance update request received",
        extra={
            "user_id": current_user.id,
            "internship_id": internship_id,
            "status": payload.status,
        },
    )

    try:
        internship = await _build_service(db).update_internship_school_insurance(
            internship_id=internship_id,
            payload=payload,
            updated_by_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if internship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Internship not found",
        )

    return internship


@router.get(
    "/students/{student_id}/internship-requirements",
    response_model=list[AdminStudentInternshipRequirementItem],
)
async def get_student_internship_requirements(
    student_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(ADMIN_READ_ROLES))],
) -> list[AdminStudentInternshipRequirementItem]:
    """Obtiene requisitos de práctica asociados a un estudiante."""

    logger.info(
        "Admin student internship requirements request received",
        extra={"user_id": current_user.id, "student_id": student_id},
    )

    service = _build_service(db)

    return await service.get_student_internship_requirements(student_id)


@router.patch(
    "/students/{student_id}/internship-requirements/{requirement_id}/status",
    response_model=AdminStudentInternshipRequirementItem,
)
async def update_student_internship_requirement_status(
    student_id: int,
    requirement_id: int,
    payload: AdminUpdateStudentInternshipRequirementStatusRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(ADMIN_READ_ROLES))],
) -> AdminStudentInternshipRequirementItem:
    """Actualiza el estado de un requisito de práctica."""

    logger.info(
        "Admin student internship requirement status update request received",
        extra={
            "user_id": current_user.id,
            "student_id": student_id,
            "requirement_id": requirement_id,
            "status": payload.status,
        },
    )

    service = _build_service(db)

    try:
        requirement = await service.update_student_internship_requirement_status(
            student_id=student_id,
            requirement_id=requirement_id,
            payload=payload,
            updated_by_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student internship requirement not found",
        )

    return requirement


@router.get(
    "/students/{student_id}/registration-requirements",
    response_model=list[AdminRegistrationRequirementItem],
)
async def get_student_registration_requirements(
    student_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_roles(SCHOOL_INSURANCE_ADMIN_ROLES)),
    ],
) -> list[AdminRegistrationRequirementItem]:
    """Obtiene prerrequisitos institucionales del estudiante."""

    logger.info(
        "Admin student registration requirements request received",
        extra={"user_id": current_user.id, "student_id": student_id},
    )

    requirements = await _build_service(db).get_student_registration_requirements(
        student_id
    )
    if requirements is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    return requirements


@router.patch(
    "/students/{student_id}/registration-requirements/school-insurance",
    response_model=AdminRegistrationRequirementItem,
)
async def update_school_insurance_requirement(
    student_id: int,
    payload: AdminUpdateSchoolInsuranceRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_roles(SCHOOL_INSURANCE_ADMIN_ROLES)),
    ],
) -> AdminRegistrationRequirementItem:
    """Registra o actualiza el seguro escolar institucional del estudiante."""

    logger.info(
        "Admin school insurance requirement update request received",
        extra={
            "user_id": current_user.id,
            "student_id": student_id,
            "is_completed": payload.is_completed,
        },
    )

    requirement = await _build_service(db).update_school_insurance_requirement(
        student_id=student_id,
        payload=payload,
        updated_by_user_id=current_user.id,
    )
    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    return requirement
