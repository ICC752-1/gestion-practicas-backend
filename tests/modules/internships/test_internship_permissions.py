from types import SimpleNamespace

import pytest

from app.modules.internships.controllers.internship_controller import (
    PRIVILEGED_READ_ROLES,
    _can_read_internship,
    _has_any_role,
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


def test_has_any_role_returns_true_when_user_has_allowed_role() -> None:
    user = _user(user_id=1, roles=["Estudiante", "Encargado de practica"])

    assert _has_any_role(user, {"Encargado de practica"})


def test_has_any_role_returns_false_when_user_lacks_allowed_roles() -> None:
    user = _user(user_id=1, roles=["Estudiante"])

    assert not _has_any_role(user, {"Director de carrera"})


def test_can_read_internship_allows_owner_without_privileged_role() -> None:
    user = _user(user_id=1, roles=["Estudiante"])
    internship = _internship(user_id=1)

    assert _can_read_internship(user, internship)


@pytest.mark.parametrize("role_name", sorted(PRIVILEGED_READ_ROLES))
def test_can_read_internship_allows_privileged_role_for_non_owner(
    role_name: str,
) -> None:
    user = _user(user_id=2, roles=[role_name])
    internship = _internship(user_id=1)

    assert _can_read_internship(user, internship)


def test_can_read_internship_rejects_non_owner_without_privileged_role() -> None:
    user = _user(user_id=2, roles=["Estudiante"])
    internship = _internship(user_id=1)

    assert not _can_read_internship(user, internship)
