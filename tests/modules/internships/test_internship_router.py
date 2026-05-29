from collections.abc import AsyncGenerator
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.database.database import get_db
from app.main import app
from app.modules.auth.dependencies.auth_dependency import get_current_user


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


async def _override_get_db() -> AsyncGenerator[None, None]:
    yield None


async def _override_current_student() -> SimpleNamespace:
    return _user(user_id=1, roles=["Estudiante"])


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


def test_dashboard_internships_rejects_student_role() -> None:
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_current_student

    try:
        with TestClient(app) as client:
            response = client.get("/internships")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
