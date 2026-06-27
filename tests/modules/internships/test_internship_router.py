from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.internships.controllers import internship_controller
from app.modules.internships.controllers.internship_controller import (
    DASHBOARD_READ_ROLES,
)

def _user(user_id: int, roles: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        roles=[
            SimpleNamespace(role=SimpleNamespace(name=role_name))
            for role_name in roles
        ],
    )


def _internship(user_id: int) -> SimpleNamespace:
    return SimpleNamespace(user_id=user_id)


class FakeTrackingService:
    def __init__(
        self,
        internship: SimpleNamespace | None,
        history: list | None = None,
    ) -> None:
        self.internship = internship
        self.history = [] if history is None else history
        self.requested_internship_id = None
        self.requested_tracking_id = None

    async def get_internship(self, internship_id: int):
        self.requested_internship_id = internship_id

        return self.internship

    async def list_internship_tracking(self, internship_id: int):
        self.requested_tracking_id = internship_id

        return self.history

async def test_dashboard_internships_rejects_student_role() -> None:
    role_checker = require_roles(DASHBOARD_READ_ROLES)

    with pytest.raises(HTTPException) as exc_info:
        await role_checker(_user(user_id=1, roles=["Estudiante"]))

    assert exc_info.value.status_code == 403


async def test_get_internship_tracking_allows_owner(monkeypatch) -> None:
    service = FakeTrackingService(internship=_internship(user_id=1))
    monkeypatch.setattr(
        internship_controller,
        "_build_service",
        lambda db: service,
    )

    tracking = await internship_controller.get_internship_tracking(
        internship_id=7,
        db=object(),
        current_user=_user(user_id=1, roles=["Estudiante"]),
    )

    assert tracking == []
    assert service.requested_internship_id == 7
    assert service.requested_tracking_id == 7


async def test_get_internship_tracking_allows_privileged_role(monkeypatch) -> None:
    service = FakeTrackingService(internship=_internship(user_id=1))
    monkeypatch.setattr(
        internship_controller,
        "_build_service",
        lambda db: service,
    )

    tracking = await internship_controller.get_internship_tracking(
        internship_id=7,
        db=object(),
        current_user=_user(user_id=2, roles=["Encargado de practica"]),
    )

    assert tracking == []


async def test_get_internship_tracking_rejects_forbidden_user(monkeypatch) -> None:
    service = FakeTrackingService(internship=_internship(user_id=1))
    monkeypatch.setattr(
        internship_controller,
        "_build_service",
        lambda db: service,
    )

    with pytest.raises(HTTPException) as exc_info:
        await internship_controller.get_internship_tracking(
            internship_id=7,
            db=object(),
            current_user=_user(user_id=2, roles=["Estudiante"]),
        )

    assert exc_info.value.status_code == 403


async def test_get_internship_tracking_returns_not_found(monkeypatch) -> None:
    service = FakeTrackingService(internship=None)
    monkeypatch.setattr(
        internship_controller,
        "_build_service",
        lambda db: service,
    )

    with pytest.raises(HTTPException) as exc_info:
        await internship_controller.get_internship_tracking(
            internship_id=404,
            db=object(),
            current_user=_user(user_id=1, roles=["Estudiante"]),
        )

    assert exc_info.value.status_code == 404
