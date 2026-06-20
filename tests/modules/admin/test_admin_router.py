from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.modules.admin.controllers.admin_controller import (
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
async def test_school_insurance_admin_roles_are_authorized(role: str) -> None:
    dependency = require_roles(SCHOOL_INSURANCE_ADMIN_ROLES)

    result = await dependency(_user(role))

    assert result.roles[0].role.name == role


async def test_school_insurance_student_role_is_rejected() -> None:
    dependency = require_roles(SCHOOL_INSURANCE_ADMIN_ROLES)

    with pytest.raises(HTTPException) as exc_info:
        await dependency(_user("Estudiante"))

    assert exc_info.value.status_code == 403


async def test_get_internship_detail_returns_404_when_missing(monkeypatch) -> None:
    from app.modules.admin.controllers import admin_controller

    service = SimpleNamespace(get_internship_detail=AsyncMock(return_value=None))
    monkeypatch.setattr(admin_controller, "_build_service", lambda db: service)

    with pytest.raises(HTTPException) as exc_info:
        await admin_controller.get_internship_detail(
            internship_id=404,
            db=object(),
            current_user=_user("Encargado de practica"),
        )

    assert exc_info.value.status_code == 404


async def test_update_student_requirement_returns_400_for_invalid_transition(
    monkeypatch,
) -> None:
    from app.modules.admin.controllers import admin_controller
    from app.modules.admin.schemas.admin_schema import (
        AdminUpdateStudentInternshipRequirementStatusRequest,
    )

    service = SimpleNamespace(
        update_student_internship_requirement_status=AsyncMock(
            side_effect=ValueError("Invalid status transition"),
        )
    )
    monkeypatch.setattr(admin_controller, "_build_service", lambda db: service)

    with pytest.raises(HTTPException) as exc_info:
        await admin_controller.update_student_internship_requirement_status(
            student_id=7,
            requirement_id=3,
            payload=AdminUpdateStudentInternshipRequirementStatusRequest(
                status="Aprobada",
            ),
            db=object(),
            current_user=_user("Encargado de practica"),
        )

    assert exc_info.value.status_code == 400


async def test_update_student_requirement_returns_404_when_missing(
    monkeypatch,
) -> None:
    from app.modules.admin.controllers import admin_controller
    from app.modules.admin.schemas.admin_schema import (
        AdminUpdateStudentInternshipRequirementStatusRequest,
    )

    service = SimpleNamespace(
        update_student_internship_requirement_status=AsyncMock(
            return_value=None,
        )
    )
    monkeypatch.setattr(admin_controller, "_build_service", lambda db: service)

    with pytest.raises(HTTPException) as exc_info:
        await admin_controller.update_student_internship_requirement_status(
            student_id=7,
            requirement_id=404,
            payload=AdminUpdateStudentInternshipRequirementStatusRequest(
                status="Habilitada",
            ),
            db=object(),
            current_user=_user("Encargado de practica"),
        )

    assert exc_info.value.status_code == 404


async def test_school_insurance_returns_404_for_non_student(monkeypatch) -> None:
    from app.modules.admin.controllers import admin_controller
    from app.modules.admin.schemas.admin_schema import AdminUpdateSchoolInsuranceRequest

    service = SimpleNamespace(
        update_school_insurance_requirement=AsyncMock(return_value=None)
    )
    monkeypatch.setattr(admin_controller, "_build_service", lambda db: service)

    with pytest.raises(HTTPException) as exc_info:
        await admin_controller.update_school_insurance_requirement(
            student_id=7,
            payload=AdminUpdateSchoolInsuranceRequest(is_completed=True),
            db=object(),
            current_user=_user("Director de carrera"),
        )

    assert exc_info.value.status_code == 404
