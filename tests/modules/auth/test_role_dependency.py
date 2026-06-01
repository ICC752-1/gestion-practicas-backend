import pytest
from fastapi import HTTPException

from app.modules.auth.dependencies.role_dependency import require_roles


class FakeUser:
    def __init__(self, roles: list[str]):
        self.id = 1
        self.roles = [
            type(
                "UserRole",
                (),
                {"role": type("RoleName", (), {"name": role})()},
            )
            for role in roles
        ]


async def test_require_roles_allows_when_role_present() -> None:
    dependency = require_roles(["Encargado de practica"])

    user = FakeUser(["Encargado de practica"])

    result = await dependency(user)

    assert result is user


async def test_require_roles_rejects_when_role_missing() -> None:
    dependency = require_roles(["Director de carrera"])

    user = FakeUser(["Estudiante"])

    with pytest.raises(HTTPException) as excinfo:
        await dependency(user)

    assert excinfo.value.status_code == 403
