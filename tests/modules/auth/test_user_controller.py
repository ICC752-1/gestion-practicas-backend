from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.auth.controllers.user_controller import (
    _ensure_can_remove_superadmin_access,
    _ensure_student_scope,
)
from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.auth.utils.roles import SUPERADMIN_ROLE, USER_ADMIN_ROLES


def _user(user_id: int, *roles: str, is_active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        is_active=is_active,
        roles=[
            SimpleNamespace(role=SimpleNamespace(name=role))
            for role in roles
        ],
    )


class FakeUserRepository:
    def __init__(self, active_superadmins: int) -> None:
        self.active_superadmins = active_superadmins

    async def count_active_users_with_role(self, role_name: str) -> int:
        assert role_name == SUPERADMIN_ROLE
        return self.active_superadmins


@pytest.mark.parametrize(
    "role",
    [
        "Encargado de practica",
        "Director de carrera",
        "Secretaria de Carrera",
        "Supervisor de practica",
        "Estudiante",
        "FICA",
    ],
)
async def test_user_admin_policy_rejects_non_superadmin_roles(role: str) -> None:
    dependency = require_roles(USER_ADMIN_ROLES)

    with pytest.raises(HTTPException) as exc_info:
        await dependency(_user(1, role))

    assert exc_info.value.status_code == 403


async def test_user_admin_policy_allows_superadmin() -> None:
    dependency = require_roles(USER_ADMIN_ROLES)
    user = _user(1, SUPERADMIN_ROLE)

    result = await dependency(user)

    assert result is user


def test_student_scope_allows_student_only_account() -> None:
    _ensure_student_scope(_user(2, "Estudiante"))


@pytest.mark.parametrize(
    "roles",
    [
        ["Director de carrera"],
        ["Estudiante", "Director de carrera"],
    ],
)
def test_student_scope_rejects_non_student_only_accounts(roles: list[str]) -> None:
    with pytest.raises(HTTPException) as exc_info:
        _ensure_student_scope(_user(2, *roles))

    assert exc_info.value.status_code == 403


async def test_superadmin_cannot_remove_own_admin_access() -> None:
    user = _user(1, SUPERADMIN_ROLE)


    with pytest.raises(HTTPException) as exc_info:
        await _ensure_can_remove_superadmin_access(
            actor=user,
            target=user,
            user_repository=FakeUserRepository(active_superadmins=2),
        )

    assert exc_info.value.status_code == 409


async def test_cannot_remove_last_active_superadmin() -> None:
    actor = _user(1, SUPERADMIN_ROLE)
    target = _user(2, SUPERADMIN_ROLE)

    with pytest.raises(HTTPException) as exc_info:
        await _ensure_can_remove_superadmin_access(
            actor=actor,
            target=target,
            user_repository=FakeUserRepository(active_superadmins=1),
        )

    assert exc_info.value.status_code == 409


async def test_can_remove_superadmin_access_when_another_active_admin_remains() -> None:
    await _ensure_can_remove_superadmin_access(
        actor=_user(1, SUPERADMIN_ROLE),
        target=_user(2, SUPERADMIN_ROLE),
        user_repository=FakeUserRepository(active_superadmins=2),
    )
