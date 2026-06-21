from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.main import app
from app.modules.admin.controllers.admin_controller import (
    ADMIN_READ_ROLES,
    SCHOOL_INSURANCE_ADMIN_ROLES,
)
from app.modules.auth.dependencies.role_dependency import require_roles


def _methods_for_path(path: str) -> set[str]:
    methods: set[str] = set()

    for route in app.routes:
        if route.path == path and hasattr(route, "methods"):
            methods.update(route.methods)

    return methods


def _user(*roles: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        roles=[
            SimpleNamespace(role=SimpleNamespace(name=role))
            for role in roles
        ],
    )


def test_school_insurance_admin_routes_are_registered() -> None:
    list_path = "/admin/students/{student_id}/registration-requirements"
    update_path = (
        "/admin/students/{student_id}/registration-requirements/school-insurance"
    )
    internship_update_path = "/admin/internships/{internship_id}/school-insurance"

    assert "GET" in _methods_for_path(list_path)
    assert "PATCH" in _methods_for_path(update_path)
    assert "PATCH" in _methods_for_path(internship_update_path)


@pytest.mark.parametrize(
    "path",
    [
        "/admin/summary",
        "/admin/students",
        "/admin/internships",
        "/admin/internships/{internship_id}",
        "/admin/students/{student_id}/internship-requirements",
        "/admin/students/{student_id}/internship-requirements/{requirement_id}/status",
    ],
)
def test_admin_read_routes_are_registered(path: str) -> None:
    assert _methods_for_path(path)


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


@pytest.mark.parametrize(
    "role",
    ["Encargado de practica", "Director de carrera"],
)
async def test_school_insurance_admin_roles_are_authorized(role: str) -> None:
    dependency = require_roles(SCHOOL_INSURANCE_ADMIN_ROLES)

    result = await dependency(_user(role))

    assert result.roles[0].role.name == role


async def test_school_insurance_student_role_is_rejected() -> None:
    dependency = require_roles(SCHOOL_INSURANCE_ADMIN_ROLES)

    with pytest.raises(HTTPException) as exc_info:
        await dependency(_user("Estudiante"))

    assert exc_info.value.status_code == 403
