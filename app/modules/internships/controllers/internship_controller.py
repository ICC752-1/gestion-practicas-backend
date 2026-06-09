"""Controlador HTTP para endpoints de practicas.

Este modulo define las rutas relacionadas con la creacion y consulta de
practicas profesionales. El controlador coordina dependencias de autenticacion,
sesion de base de datos y servicios de dominio, manteniendo la logica de negocio
principal en `InternshipService`.
"""
import logging

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.database import get_db
from app.core.config import config
from app.modules.auth.dependencies.auth_dependency import get_current_user
from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.auth.models.user_model import User
from app.modules.internships.models.internship_model import Internship
from app.modules.internships.repositories.internship_repository import (
    InternshipRepository,
)
from app.modules.internships.schemas.internship_schema import (
    DashboardInternshipStatus,
    InternshipActionRequest,
    InternshipActionResponse,
    InternshipCreateRequest,
    InternshipDashboardListItem,
    InternshipDashboardStatsResponse,
    InternshipResponse,
    InternshipTrackingResponse,
)
from app.modules.internships.services.internship_service import InternshipService

from app.modules.internships.schemas.internship_schema import (
    InternshipExceptionRequest,
    InternshipExceptionResponse,
)

from app.modules.notifications.repositories.notification_repository import (
    NotificationRepository,
)
from app.modules.notifications.services.notification_service import (
    NotificationService,

)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/internships", tags=["Internships"])

STUDENT_ROLE = "Estudiante"
DASHBOARD_READ_ROLES = [
    "Encargado de practica",
    "Director de carrera",
]
PRIVILEGED_READ_ROLES = {
    "Encargado de practica",
    "Director de carrera",
    "Secretaria de Carrera",
}

ACTION_ROLES = [
    "Encargado de practica", 
    "Director de carrera", 
    "Secretaria de Carrera"]

EXCEPTION_ROLES = [
    "Encargado de practica", 
    "Director de carrera"]

def _has_any_role(user: User, role_names: set[str]) -> bool:
    """Verifica si un usuario posee al menos uno de los roles indicados.

    Args:
        user: Usuario autenticado con sus roles cargados.
        role_names: Conjunto de nombres de roles permitidos.

    Returns:
        `True` si el usuario posee al menos uno de los roles; `False` en caso
        contrario.
    """

    return any(user_role.role.name in role_names for user_role in user.roles)


def _can_read_internship(user: User, internship: Internship) -> bool:
    """Determina si un usuario puede consultar una practica.

    La lectura esta permitida cuando el usuario es propietario de la practica o
    cuando posee un rol privilegiado de revision.

    Args:
        user: Usuario autenticado que intenta acceder al recurso.
        internship: Practica solicitada.

    Returns:
        `True` si el usuario puede leer la practica; `False` si no tiene
        permisos suficientes.
    """

    return internship.user_id == user.id or _has_any_role(user, PRIVILEGED_READ_ROLES)


def _build_service(db: AsyncSession) -> InternshipService:
    """Construye el servicio de practicas para un request.

    Args:
        db: Sesion asincrona de SQLAlchemy inyectada por FastAPI.

    Returns:
        Instancia de `InternshipService` configurada con su repositorio
        y servicio de notificaciones.
    """

    notification_service = NotificationService(
        notification_repository=NotificationRepository(db),
        app_config=config,
    )

    return InternshipService(
        internship_repository=InternshipRepository(db),
        notification_service=notification_service,
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
    """Crea una practica asociada al estudiante autenticado.

    Solo usuarios con rol `Estudiante` pueden crear practicas. La practica queda
    asociada al identificador del usuario autenticado.

    Args:
        internship_data: Payload con los datos base de la practica.
        db: Sesion asincrona de base de datos inyectada por `get_db`.
        current_user: Usuario autenticado validado por `require_roles`.

    Returns:
        `InternshipResponse` con la practica persistida.
    """

    service = _build_service(db)
    internship = await service.create_internship(
        internship_data=internship_data,
        user_id=current_user.id,
    )

    return InternshipResponse.model_validate(internship)


@router.get("", response_model=list[InternshipDashboardListItem])
async def list_dashboard_internships(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(DASHBOARD_READ_ROLES))],
    status_filter: Annotated[
        DashboardInternshipStatus | None,
        Query(alias="status"),
    ] = None,
) -> list[InternshipDashboardListItem]:
    """Lista practicas para el dashboard de coordinador/director.

    Args:
        db: Sesion asincrona de base de datos inyectada por `get_db`.
        current_user: Usuario autenticado con rol autorizado por `require_roles`.
        status_filter: Estado normalizado opcional (`submitted`, `in_review`,
            `approved`, `rejected`).

    Returns:
        Lista de practicas con estudiante y estado normalizado para dashboard.
    """

    service = _build_service(db)

    return await service.list_dashboard_internships(status_filter=status_filter)


@router.get("/stats", response_model=InternshipDashboardStatsResponse)
async def get_dashboard_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(DASHBOARD_READ_ROLES))],
) -> InternshipDashboardStatsResponse:
    """Obtiene conteos agregados para el dashboard de coordinador/director.

    Args:
        db: Sesion asincrona de base de datos inyectada por `get_db`.
        current_user: Usuario autenticado con rol autorizado por `require_roles`.

    Returns:
        Conteos globales y por estado normalizado.
    """

    service = _build_service(db)

    return await service.get_dashboard_stats()


@router.get("/me", response_model=list[InternshipResponse])
async def list_my_internships(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[InternshipResponse]:
    """Lista las practicas asociadas al usuario autenticado.

    Args:
        db: Sesion asincrona de base de datos inyectada por `get_db`.
        current_user: Usuario autenticado obtenido desde el token Bearer.

    Returns:
        Lista de practicas cuyo `user_id` corresponde al usuario autenticado.
    """

    service = _build_service(db)
    internships = await service.list_user_internships(user_id=current_user.id)

    return [
        InternshipResponse.model_validate(internship)
        for internship in internships
    ]


@router.get(
    "/{internship_id}/tracking",
    response_model=list[InternshipTrackingResponse],
)
async def get_internship_tracking(
    internship_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[InternshipTrackingResponse]:
    """Obtiene el historial de estados de una practica.

    La consulta exige que la practica exista y que el usuario sea propietario o
    tenga un rol privilegiado de lectura.

    Args:
        internship_id: Identificador entero de la practica solicitada.
        db: Sesion asincrona de base de datos inyectada por `get_db`.
        current_user: Usuario autenticado obtenido desde el token Bearer.

    Returns:
        Lista cronologica de transiciones de estado de la practica.

    Raises:
        HTTPException: Con codigo 404 si la practica no existe.
        HTTPException: Con codigo 403 si el usuario no tiene permisos.
    """

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

    status_history = await service.list_internship_tracking(
        internship_id=internship_id,
    )

    return [
        InternshipTrackingResponse.model_validate(history)
        for history in status_history
    ]


@router.get("/{internship_id}", response_model=InternshipResponse)
async def get_internship(
    internship_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> InternshipResponse:
    """Obtiene el detalle de una practica por identificador.

    La consulta exige que la practica exista y que el usuario sea propietario o
    tenga un rol privilegiado de lectura.

    Args:
        internship_id: Identificador entero de la practica solicitada.
        db: Sesion asincrona de base de datos inyectada por `get_db`.
        current_user: Usuario autenticado obtenido desde el token Bearer.

    Returns:
        `InternshipResponse` con el detalle de la practica.

    Raises:
        HTTPException: Con codigo 404 si la practica no existe.
        HTTPException: Con codigo 403 si el usuario no tiene permisos de
            lectura sobre la practica.
    """

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

@router.post(
    "/{internship_id}/approve",
    response_model=InternshipActionResponse,
)
async def approve_internship(
    internship_id: int,
    payload: InternshipActionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(ACTION_ROLES))],
) -> InternshipActionResponse:
    """Aprueba una practica sin imponer orden secuencial entre roles.

    `Encargado de practica` y `Director de carrera` pueden aprobar desde
    `Pendiente` o `En revision`. El estado `En revision` se usa solo como
    trazabilidad opcional, no como paso obligatorio.
 
    Args:
        internship_id: Identificador de la practica a aprobar.
        payload: Payload con comentario opcional.
        db: Sesion asincrona de base de datos inyectada por `get_db`.
        current_user: Usuario autenticado con rol autorizado por `require_roles`.
 
    Returns:
        `InternshipActionResponse` con el nuevo `status_id` y el comentario.
 
    Raises:
        HTTPException 404: Si la practica no existe.
        HTTPException 403: Si el rol del actor no corresponde a la etapa actual.
        HTTPException 409: Si la practica ya esta en estado terminal o el estado
            actual no es apto para aprobacion.
    """
    logger.info("HTTP POST /internships/%s/approve - Petición de aprobación administrativa recibida del actor ID: %s", 
                internship_id, current_user.id)
 
    service = _build_service(db)
    internship = await service.approve(internship_id, current_user, payload.comment)
 
    logger.info("HTTP 200 OK - Práctica ID: %s aprobada administrativamente con éxito por actor ID: %s", 
                internship_id, current_user.id)
    return InternshipActionResponse(
        id=internship.id,
        status_id=internship.status_id,
        comment=payload.comment,
    )
 
 
@router.post(
    "/{internship_id}/reject",
    response_model=InternshipActionResponse,
)
async def reject_internship(
    internship_id: int,
    payload: InternshipActionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(ACTION_ROLES))],
) -> InternshipActionResponse:
    """Rechaza una practica que no se encuentra en estado terminal.
 
    Roles autorizados: `Encargado de practica` y `Director de carrera`.
    El comentario de rechazo es obligatorio.
 
    Args:
        internship_id: Identificador de la practica a rechazar.
        payload: Payload con el motivo del rechazo (obligatorio).
        db: Sesion asincrona de base de datos inyectada por `get_db`.
        current_user: Usuario autenticado con rol autorizado por `require_roles`.
 
    Returns:
        `InternshipActionResponse` con el nuevo `status_id` y el comentario.
 
    Raises:
        HTTPException 400: Si no se proporciona comentario.
        HTTPException 403: Si el actor no tiene permiso `reject`.
        HTTPException 404: Si la practica no existe.
        HTTPException 409: Si la practica ya fue rechazada o aprobada.
    """
    logger.info("HTTP POST /internships/%s/reject - Petición de rechazo definitivo recibida del actor ID: %s", 
                internship_id, current_user.id)
 
    service = _build_service(db)
    internship = await service.reject(internship_id, current_user, payload.comment)
 
    logger.info("HTTP 200 OK - Práctica ID: %s rechazada de forma definitiva por actor ID: %s", 
                internship_id, current_user.id)
    return InternshipActionResponse(
        id=internship.id,
        status_id=internship.status_id,
        comment=payload.comment,
    )
 
 
@router.post(
    "/{internship_id}/derive",
    response_model=InternshipActionResponse,
)
async def derive_internship(
    internship_id: int,
    payload: InternshipActionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(ACTION_ROLES))],
) -> InternshipActionResponse:
    """Deriva una practica a revision por DIRAE.
 
    Solo `Secretaria de Carrera` puede ejecutar esta accion. La practica no
    debe encontrarse en estado terminal (`Aprobada`, `Rechazada`, `Reprobada`).
    El comentario es obligatorio.
 
    Args:
        internship_id: Identificador de la practica a derivar.
        payload: Payload con el motivo de la derivacion (obligatorio).
        db: Sesion asincrona de base de datos inyectada por `get_db`.
        current_user: Usuario autenticado con rol autorizado por `require_roles`.
 
    Returns:
        `InternshipActionResponse` con el nuevo `status_id` y el comentario.
 
    Raises:
        HTTPException 400: Si no se proporciona comentario.
        HTTPException 403: Si el actor no tiene permiso `derive`.
        HTTPException 404: Si la practica no existe.
        HTTPException 409: Si la practica ya esta en estado terminal.
    """
    logger.info("HTTP POST /internships/%s/derive - Petición de derivación a DIRAE recibida del actor ID: %s", 
                internship_id, current_user.id)
 
    service = _build_service(db)
    internship = await service.derive(internship_id, current_user, payload.comment)
 
    logger.info("HTTP 200 OK - Práctica ID: %s derivada exitosamente a DIRAE por actor ID: %s", 
                internship_id, current_user.id)
    return InternshipActionResponse(
        id=internship.id,
        status_id=internship.status_id,
        comment=payload.comment,
    )


@router.post(
    "/{internship_id}/exceptions",
    response_model=InternshipExceptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant_internship_exception(
    internship_id: int,
    payload: InternshipExceptionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(EXCEPTION_ROLES))],
) -> InternshipExceptionResponse:
    """Registra una excepcion administrativa sobre una regla de negocio.

    Permite que una practica continúe su flujo pese a no cumplir la regla
    indicada. La excepcion no modifica el valor original del campo exceptuado
    ni implica cumplimiento real de la regla base.

    Args:
        internship_id: Identificador de la practica.
        payload: Regla a exceptuar y justificacion obligatoria.
        db: Sesion asincrona de base de datos.
        current_user: Usuario con rol autorizado para otorgar excepciones.

    Returns:
        ``InternshipExceptionResponse`` con responsable, fecha y regla exceptuada.

    Raises:
        HTTPException 400: Si la regla no admite excepcion o el motivo esta vacio.
        HTTPException 403: Si el actor no tiene permiso ``grant_exception``.
        HTTPException 404: Si la practica no existe.
        HTTPException 409: Si la practica esta en estado terminal.
    """
    logger.info("HTTP POST /internships/%s/exceptions - Solicitud para conceder excepción sobre regla '%s' recibida del actor ID: %s", 
                internship_id, payload.rule, current_user.id)
    
    service = _build_service(db)
    exception = await service.grant_exception(
        internship_id=internship_id,
        actor=current_user,
        rule=payload.rule,
        reason=payload.reason,
    )
    
    logger.info("HTTP 201 Created - Excepción sobre regla '%s' creada con éxito para práctica ID: %s", payload.rule, internship_id)
    return InternshipExceptionResponse.model_validate(exception)


@router.get(
    "/{internship_id}/exceptions",
    response_model=list[InternshipExceptionResponse],
)
async def list_internship_exceptions(
    internship_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[InternshipExceptionResponse]:
    """Lista las excepciones administrativas registradas para una practica.

    Accesible para el propietario de la practica y roles privilegiados.

    Args:
        internship_id: Identificador de la practica.
        db: Sesion asincrona de base de datos.
        current_user: Usuario autenticado.

    Returns:
        Lista de excepciones con responsable y fecha.

    Raises:
        HTTPException 403: Si el usuario no tiene acceso a la practica.
        HTTPException 404: Si la practica no existe.
    """
    logger.info("HTTP GET /internships/%s/exceptions - Solicitud de listado de excepciones por usuario ID: %s", 
                internship_id, current_user.id)
                
    service = _build_service(db)
    internship = await service.get_internship(internship_id)

    if internship is None:
        logger.warning("HTTP 404 Not Found - Consulta de excepciones fallida: No se encontró la práctica con ID: %s", internship_id)
        raise HTTPException(status_code=404, detail="Internship not found")

    if not _can_read_internship(user=current_user, internship=internship):
        logger.warning("HTTP 403 Forbidden - Intento no autorizado de listar excepciones de la práctica ID: %s por usuario ID: %s", 
                       internship_id, current_user.id)
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    exceptions = await service.internship_repository.list_exceptions(internship_id)
    return [InternshipExceptionResponse.model_validate(e) for e in exceptions]