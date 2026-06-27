from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.admin.controllers.admin_controller import (
    ADMIN_READ_ROLES,
    SCHOOL_INSURANCE_ADMIN_ROLES,
)
from app.modules.auth.dependencies.role_dependency import require_roles


def _user(*roles: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        roles=[
            SimpleNamespace(role=SimpleNamespace(name=role))
            for role in roles
        ],
    )


@pytest.mark.parametrize(
    "role",
    ["Encargado de practica", "Director de carrera"],
)
async def test_admin_read_roles_are_authorized(role: str) -> None:
    dependency = require_roles(ADMIN_READ_ROLES)

    result = await dependency(_user(role))

    assert result.roles[0].role.name == role


@pytest.mark.parametrize(
    "role",
    ["Secretaria de Carrera", "Estudiante", "Supervisor de practica", "FICA", "Superadmin"],
)
async def test_admin_read_rejects_non_decision_roles(role: str) -> None:
    dependency = require_roles(ADMIN_READ_ROLES)

    with pytest.raises(HTTPException) as exc_info:
        await dependency(_user(role))

    assert exc_info.value.status_code == 403


async def test_school_insurance_director_role_is_authorized() -> None:
    dependency = require_roles(SCHOOL_INSURANCE_ADMIN_ROLES)

    result = await dependency(_user("Director de carrera"))

    assert result.roles[0].role.name == "Director de carrera"


async def test_school_insurance_coordinator_role_is_rejected() -> None:
    dependency = require_roles(SCHOOL_INSURANCE_ADMIN_ROLES)

    with pytest.raises(HTTPException) as exc_info:
        await dependency(_user("Encargado de practica"))

    assert exc_info.value.status_code == 403


async def test_school_insurance_student_role_is_rejected() -> None:
    dependency = require_roles(SCHOOL_INSURANCE_ADMIN_ROLES)

    with pytest.raises(HTTPException) as exc_info:
        await dependency(_user("Estudiante"))

    assert exc_info.value.status_code == 403
