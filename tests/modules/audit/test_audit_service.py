from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.audit.controllers.audit_controller import AUDIT_ROLES
from app.modules.audit.schemas.audit_schema import AuditEventFilters
from app.modules.audit.services.audit_service import AuditService, MASKED_VALUE
from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.auth.utils.roles import SUPERADMIN_ROLE


def _user(*roles: str):
    return SimpleNamespace(
        id=1,
        roles=[SimpleNamespace(role=SimpleNamespace(name=role)) for role in roles],
    )


def _actor():
    return SimpleNamespace(
        id=7,
        email="admin@ufro.cl",
        first_name="Ada",
        last_name="Admin",
    )


def _log(**overrides):
    data = {
        "id": 10,
        "timestamp": datetime(2026, 6, 27, 12, 30),
        "action": "UPDATE",
        "entity": "Usuario",
        "entity_id": 22,
        "description": "Actualización de datos",
        "old_value": {
            "email": "user@ufro.cl",
            "is_active": True,
            "password_hash": "secret-hash",
        },
        "new_value": {
            "email": "user@ufro.cl",
            "is_active": False,
            "password_hash": "new-secret-hash",
            "profile": {"file_path": "/srv/private/document.pdf"},
        },
    }
    data.update(overrides)
    return SimpleNamespace(**data)


class FakeAuditRepository:
    def __init__(self, records=None):
        self.records = records or [(_log(), _actor())]

    async def list_events(self, filters: AuditEventFilters, *, limit: int, offset: int):
        assert limit == 20
        assert offset == 0
        return self.records

    async def count_events(self, filters: AuditEventFilters) -> int:
        return len(self.records)

    async def count_last_24_hours(self, filters: AuditEventFilters) -> int:
        return 1

    async def count_without_actor(self, filters: AuditEventFilters) -> int:
        return 0

    async def count_by_action(self, filters: AuditEventFilters) -> dict[str, int]:
        return {"UPDATE": len(self.records)}

    async def get_event(self, event_id: int):
        return next((record for record in self.records if record[0].id == event_id), None)


async def test_audit_service_returns_sanitized_list_summary() -> None:
    service = AuditService(FakeAuditRepository())

    response = await service.list_events(AuditEventFilters(), limit=20, offset=0)

    assert response.total == 1
    assert response.stats.by_action == {"UPDATE": 1}
    assert response.items[0].actor.email == "admin@ufro.cl"
    assert response.items[0].changed_fields == ["is_active", "profile"]
    assert "password_hash" not in response.items[0].changed_fields
    assert response.items[0].change_preview[0] == "is_active: true -> false"


async def test_audit_detail_masks_sensitive_values() -> None:
    service = AuditService(FakeAuditRepository())

    detail = await service.get_event(10)

    assert detail.old_value["password_hash"] == MASKED_VALUE
    assert detail.new_value["password_hash"] == MASKED_VALUE
    assert detail.new_value["profile"]["file_path"] == MASKED_VALUE


async def test_audit_detail_returns_404_when_event_does_not_exist() -> None:
    service = AuditService(FakeAuditRepository(records=[]))

    with pytest.raises(HTTPException) as exc_info:
        await service.get_event(999)

    assert exc_info.value.status_code == 404


async def test_audit_policy_allows_superadmin() -> None:
    dependency = require_roles(AUDIT_ROLES)
    user = _user(SUPERADMIN_ROLE)

    result = await dependency(user)

    assert result is user


@pytest.mark.parametrize(
    "role",
    [
        "Estudiante",
        "Encargado de practica",
        "Director de carrera",
        "Secretaria de Carrera",
        "Supervisor de practica",
        "FICA",
    ],
)
async def test_audit_policy_rejects_non_superadmin_roles(role: str) -> None:
    dependency = require_roles(AUDIT_ROLES)

    with pytest.raises(HTTPException) as exc_info:
        await dependency(_user(role))

    assert exc_info.value.status_code == 403
