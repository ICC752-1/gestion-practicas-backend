"""Schemas HTTP para consulta de auditoria funcional."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.audit.models.audit_log_model import AuditActionEnum, AuditEntityEnum


class AuditEventFilters(BaseModel):
    """Filtros disponibles para consultar LogAction."""

    date_from: date | None = None
    date_to: date | None = None
    action: AuditActionEnum | None = None
    entity: AuditEntityEnum | None = None
    actor_id: int | None = None
    entity_id: int | None = None
    search: str | None = None
    without_actor: bool = False


class AuditActor(BaseModel):
    """Actor asociado a un evento de auditoria."""

    id: int
    email: str
    name: str


class AuditStats(BaseModel):
    """Resumen numerico para el panel de auditoria."""

    total: int
    last_24_hours: int
    without_actor: int
    by_action: dict[str, int] = Field(default_factory=dict)


class AuditEventListItem(BaseModel):
    """Evento resumido para listados."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    action: str
    entity: str
    entity_id: int
    description: str
    actor: AuditActor | None
    changed_fields: list[str]
    change_preview: list[str]


class AuditEventListResponse(BaseModel):
    """Respuesta paginada para la tabla de auditoria."""

    generated_at: datetime
    items: list[AuditEventListItem]
    total: int
    limit: int
    offset: int
    stats: AuditStats


class AuditEventDetail(AuditEventListItem):
    """Detalle sanitizado de un evento de auditoria."""

    old_value: dict | list | str | int | float | bool | None
    new_value: dict | list | str | int | float | bool | None
