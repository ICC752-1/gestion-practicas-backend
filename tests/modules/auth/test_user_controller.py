from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.auth.controllers.user_controller import (
    _build_academic_progress_by_user,
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


def test_build_academic_progress_marks_current_practice() -> None:
    requirements = [
        SimpleNamespace(
            user_id=7,
            type="Práctica de Estudio I",
            status="Aprobada",
        ),
        SimpleNamespace(
            user_id=7,
            type="Práctica de Estudio II",
            status="Habilitada",
        ),
    ]
    internships = [
        SimpleNamespace(
            id=11,
            user_id=7,
            internship_type="Práctica de Estudio I",
            status=SimpleNamespace(title="Aprobada"),
            completion_status="finalized",
            final_result="passed",
            is_cancelled=False,
        ),
        SimpleNamespace(
            id=12,
            user_id=7,
            internship_type="Práctica de Estudio II",
            status=SimpleNamespace(title="Aprobada"),
            completion_status="in_progress",
            final_result="pending",
            is_cancelled=False,
        ),
    ]

    progress = _build_academic_progress_by_user(
        user_ids=[7],
        requirements=requirements,
        internships=internships,
    )[7]

    assert progress.completed_count == 1
    assert progress.total_count == 3
    assert progress.current_type == "Práctica de Estudio II"
    assert progress.current_label == "Práctica de Estudio II"
    assert progress.current_status == "En curso"
    assert [item.type for item in progress.items] == [
        "Práctica de Estudio I",
        "Práctica de Estudio II",
        None,
    ]
    assert progress.items[2].label == "Práctica Controlada o Tesis"
    assert progress.items[2].available_types == [
        "Práctica Controlada",
        "Tesis",
    ]
    assert progress.items[0].is_completed is True
    assert progress.items[1].is_current is True


def test_academic_progress_does_not_complete_an_approved_request() -> None:
    requirements = [
        SimpleNamespace(
            user_id=7,
            type="Práctica de Estudio I",
            status="Aprobada",
        ),
    ]
    internships = [
        SimpleNamespace(
            id=11,
            user_id=7,
            internship_type="Práctica de Estudio I",
            status=SimpleNamespace(title="Aprobada"),
            completion_status="not_started",
            final_result="pending",
            is_cancelled=False,
        ),
    ]

    progress = _build_academic_progress_by_user(
        user_ids=[7],
        requirements=requirements,
        internships=internships,
    )[7]

    assert progress.completed_count == 0
    assert progress.current_type == "Práctica de Estudio I"
    assert progress.current_status == "Solicitud aprobada"
    assert progress.items[0].is_completed is False


def test_academic_progress_counts_one_selected_final_option() -> None:
    practice_types = [
        "Práctica de Estudio I",
        "Práctica de Estudio II",
        "Tesis",
    ]
    requirements = [
        SimpleNamespace(user_id=7, type=practice_type, status="Aprobada")
        for practice_type in practice_types
    ]
    internships = [
        SimpleNamespace(
            id=index,
            user_id=7,
            internship_type=practice_type,
            status=SimpleNamespace(title="Aprobada"),
            completion_status="finalized",
            final_result="passed",
            is_cancelled=False,
        )
        for index, practice_type in enumerate(practice_types, start=11)
    ]

    progress = _build_academic_progress_by_user(
        user_ids=[7],
        requirements=requirements,
        internships=internships,
    )[7]

    assert progress.completed_count == 3
    assert progress.total_count == 3
    assert progress.current_type is None
    assert progress.items[2].type == "Tesis"
    assert progress.items[2].label == "Tesis"
    assert progress.items[2].is_completed is True
