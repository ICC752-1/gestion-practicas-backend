from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.main import app
from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.internships.controllers.internship_controller import (
    DASHBOARD_READ_ROLES,
)


def _methods_for_path(path: str) -> set[str]:
    methods: set[str] = set()

    for route in app.routes:
        if route.path == path and hasattr(route, "methods"):
            methods.update(route.methods)

    return methods


def _user(user_id: int, roles: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        roles=[
            SimpleNamespace(role=SimpleNamespace(name=role_name))
            for role_name in roles
        ],
    )


def test_internships_router_is_registered() -> None:
    paths = {route.path for route in app.routes}

    assert "/internships" in paths
    assert "GET" in _methods_for_path("/internships")
    assert "POST" in _methods_for_path("/internships")
    assert "/internships/stats" in paths
    assert "GET" in _methods_for_path("/internships/stats")
    assert "/internships/me" in paths
    assert "/internships/{internship_id}" in paths


def test_users_and_roles_routers_are_registered() -> None:
    paths = {route.path for route in app.routes}

    assert "/users" in paths
    assert "/users/{user_id}" in paths
    assert "/users/{user_id}/roles" in paths
    assert "/users/{user_id}/roles/{role_id}" in paths
    assert "/roles" in paths
    assert "/roles/{role_id}" in paths


async def test_dashboard_internships_rejects_student_role() -> None:
    role_checker = require_roles(DASHBOARD_READ_ROLES)

    with pytest.raises(HTTPException) as exc_info:
        await role_checker(_user(user_id=1, roles=["Estudiante"]))

    assert exc_info.value.status_code == 403
