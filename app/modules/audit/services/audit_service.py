"""Servicio de consulta y sanitizacion de auditoria."""

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status

from app.modules.audit.models.audit_log_model import AuditLog
from app.modules.audit.repositories.audit_repository import AuditRepository
from app.modules.audit.schemas.audit_schema import (
    AuditActor,
    AuditEventDetail,
    AuditEventFilters,
    AuditEventListItem,
    AuditEventListResponse,
    AuditStats,
)
from app.modules.auth.models.user_model import User

SENSITIVE_KEY_PARTS = (
    "password",
    "token",
    "hash",
    "secret",
    "jti",
    "file_path",
    "storage_path",
    "path",
)
MASKED_VALUE = "[oculto]"


class AuditService:
    """Orquesta la consulta segura de eventos de auditoria."""

    def __init__(self, repository: AuditRepository) -> None:
        self.repository = repository

    async def list_events(
        self,
        filters: AuditEventFilters,
        *,
        limit: int,
        offset: int,
    ) -> AuditEventListResponse:
        items = await self.repository.list_events(filters, limit=limit, offset=offset)
        total = await self.repository.count_events(filters)
        stats = AuditStats(
            total=total,
            last_24_hours=await self.repository.count_last_24_hours(filters),
            without_actor=await self.repository.count_without_actor(filters),
            by_action=await self.repository.count_by_action(filters),
        )

        return AuditEventListResponse(
            generated_at=datetime.now(UTC),
            items=[self._to_list_item(log, actor) for log, actor in items],
            total=total,
            limit=limit,
            offset=offset,
            stats=stats,
        )

    async def get_event(self, event_id: int) -> AuditEventDetail:
        record = await self.repository.get_event(event_id)

        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit event not found",
            )

        log, actor = record
        item = self._to_list_item(log, actor)

        return AuditEventDetail(
            **item.model_dump(),
            old_value=self._sanitize(log.old_value),
            new_value=self._sanitize(log.new_value),
        )

    def _to_list_item(self, log: AuditLog, actor: User | None) -> AuditEventListItem:
        changed_fields = self._changed_fields(log.old_value, log.new_value)

        return AuditEventListItem(
            id=log.id,
            timestamp=log.timestamp,
            action=self._enum_value(log.action),
            entity=self._enum_value(log.entity),
            entity_id=log.entity_id,
            description=log.description,
            actor=self._actor(actor),
            changed_fields=changed_fields,
            change_preview=self._change_preview(log, changed_fields),
        )

    def _actor(self, actor: User | None) -> AuditActor | None:
        if actor is None:
            return None

        name = f"{actor.first_name} {actor.last_name}".strip()

        return AuditActor(
            id=actor.id,
            email=actor.email,
            name=name or actor.email,
        )

    def _changed_fields(
        self,
        old_value: dict[str, Any] | None,
        new_value: dict[str, Any] | None,
    ) -> list[str]:
        old_data = old_value if isinstance(old_value, dict) else {}
        new_data = new_value if isinstance(new_value, dict) else {}
        changed = []

        for key in sorted(set(old_data) | set(new_data)):
            if self._is_sensitive_key(key):
                continue
            if old_data.get(key) != new_data.get(key):
                changed.append(key)

        return changed

    def _change_preview(self, log: AuditLog, changed_fields: list[str]) -> list[str]:
        action = self._enum_value(log.action)

        if action == "INSERT":
            return ["Registro creado"]
        if action == "DELETE":
            return ["Registro eliminado"]
        if not changed_fields:
            return ["Sin cambios visibles o solo campos sensibles ocultos"]

        old_data = log.old_value if isinstance(log.old_value, dict) else {}
        new_data = log.new_value if isinstance(log.new_value, dict) else {}
        preview = []

        for field in changed_fields[:4]:
            old = self._summarize_value(old_data.get(field))
            new = self._summarize_value(new_data.get(field))
            preview.append(f"{field}: {old} -> {new}")

        if len(changed_fields) > 4:
            preview.append(f"+{len(changed_fields) - 4} campos mas")

        return preview

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: MASKED_VALUE if self._is_sensitive_key(key) else self._sanitize(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._sanitize(item) for item in value]

        return value

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        normalized = key.lower()
        return any(part in normalized for part in SENSITIVE_KEY_PARTS)

    def _summarize_value(self, value: Any) -> str:
        sanitized = self._sanitize(value)

        if sanitized is None:
            return "N/A"
        if isinstance(sanitized, bool):
            return "true" if sanitized else "false"
        if isinstance(sanitized, (dict, list)):
            return "valor estructurado"

        text = str(sanitized)
        return text if len(text) <= 42 else f"{text[:39]}..."

    @staticmethod
    def _enum_value(value) -> str:
        return getattr(value, "value", value)
