"""Controlador HTTP para auditoria funcional."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.database import get_db
from app.modules.audit.models.audit_log_model import AuditActionEnum, AuditEntityEnum
from app.modules.audit.repositories.audit_repository import AuditRepository
from app.modules.audit.schemas.audit_schema import (
    AuditEventDetail,
    AuditEventFilters,
    AuditEventListResponse,
)
from app.modules.audit.services.audit_service import AuditService
from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.auth.models.user_model import User
from app.modules.auth.utils.roles import SUPERADMIN_ROLE

AUDIT_ROLES = [SUPERADMIN_ROLE]

router = APIRouter(prefix="/audit", tags=["Audit"])


def _build_service(db: AsyncSession) -> AuditService:
    return AuditService(AuditRepository(db))


def _build_filters(
    date_from: date | None,
    date_to: date | None,
    action: AuditActionEnum | None,
    entity: AuditEntityEnum | None,
    actor_id: int | None,
    entity_id: int | None,
    search: str | None,
    without_actor: bool,
) -> AuditEventFilters:
    return AuditEventFilters(
        date_from=date_from,
        date_to=date_to,
        action=action,
        entity=entity,
        actor_id=actor_id,
        entity_id=entity_id,
        search=search.strip() if search else None,
        without_actor=without_actor,
    )


@router.get("/events", response_model=AuditEventListResponse)
async def list_audit_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(AUDIT_ROLES))],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    action: Annotated[AuditActionEnum | None, Query()] = None,
    entity: Annotated[AuditEntityEnum | None, Query()] = None,
    actor_id: Annotated[int | None, Query(ge=1)] = None,
    entity_id: Annotated[int | None, Query(ge=1)] = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
    without_actor: Annotated[bool, Query()] = False,
) -> AuditEventListResponse:
    """Lista eventos de auditoria para Superadmin."""

    del current_user
    filters = _build_filters(
        date_from=date_from,
        date_to=date_to,
        action=action,
        entity=entity,
        actor_id=actor_id,
        entity_id=entity_id,
        search=search,
        without_actor=without_actor,
    )

    return await _build_service(db).list_events(filters, limit=limit, offset=offset)


@router.get("/events/{event_id}", response_model=AuditEventDetail)
async def get_audit_event(
    event_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(AUDIT_ROLES))],
) -> AuditEventDetail:
    """Obtiene el detalle sanitizado de un evento de auditoria."""

    del current_user
    return await _build_service(db).get_event(event_id)
