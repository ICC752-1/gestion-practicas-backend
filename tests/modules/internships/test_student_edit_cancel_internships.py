"""Tests para correccion y anulacion reciente del estudiante propietario."""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.internships.schemas.internship_schema import (
    StudentInternshipUpdateRequest,
)
from app.modules.internships.services.internship_service import InternshipService


def _state(title: str, state_id: int = 1) -> SimpleNamespace:
    return SimpleNamespace(id=state_id, title=title)


def _history(action: str | None = None) -> SimpleNamespace:
    metadata = {"event": "internship_created"} if action is None else {"action": action}
    return SimpleNamespace(metadata_json=metadata)


def _user(user_id: int = 10) -> SimpleNamespace:
    return SimpleNamespace(id=user_id, roles=[])


def _internship(
    *,
    user_id: int = 10,
    status_title: str = "Pendiente",
    hours_old: int = 1,
    is_cancelled: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        user_id=user_id,
        status_id=1,
        status=_state(status_title),
        is_cancelled=is_cancelled,
        blocks_new_registration=True,
        upload_date=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=hours_old),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 1),
        city="Temuco",
        org_name="Empresa anterior",
    )


class FakeStudentEditRepository:
    def __init__(
        self,
        internship: SimpleNamespace | None,
        history: list[SimpleNamespace] | None = None,
    ) -> None:
        self.internship = internship
        self.history = history or [_history()]
        self.updated_kwargs = None
        self.cancelled_kwargs = None

    async def get_internship_by_id(self, internship_id: int):
        return self.internship

    async def list_internship_status_history(self, internship_id: int):
        return self.history

    async def update_internship_admin_fields_with_history(self, **kwargs):
        self.updated_kwargs = kwargs
        for field_name, value in kwargs["updates"].items():
            setattr(kwargs["internship"], field_name, value)
        return kwargs["internship"]

    async def cancel_internship_with_history(self, **kwargs):
        self.cancelled_kwargs = kwargs
        internship = kwargs["internship"]
        internship.is_cancelled = True
        internship.cancelled_by = kwargs["actor_id"]
        internship.cancellation_reason = kwargs["reason"]
        internship.blocks_new_registration = False
        return internship


def _service(
    internship: SimpleNamespace | None,
    history: list[SimpleNamespace] | None = None,
) -> tuple[InternshipService, FakeStudentEditRepository]:
    repository = FakeStudentEditRepository(internship, history)
    return (
        InternshipService(
            internship_repository=repository,
            student_edit_window_hours=24,
        ),
        repository,
    )


async def test_student_actions_available_for_owner_pending_within_window() -> None:
    service, _ = _service(_internship())

    availability = await service.get_student_action_availability(
        internship_id=7,
        actor=_user(),
    )

    assert availability.can_update is True
    assert availability.can_cancel is True
    assert availability.reasons == []
    assert availability.editable_until is not None


async def test_student_update_records_reason_action_and_changed_fields() -> None:
    service, repository = _service(_internship())
    payload = StudentInternshipUpdateRequest(
        reason="  Error en ciudad  ",
        city="Padre Las Casas",
    )

    result = await service.update_student_fields(
        internship_id=7,
        actor=_user(),
        payload=payload,
    )

    assert result.city == "Padre Las Casas"
    assert repository.updated_kwargs["actor_id"] == 10
    assert repository.updated_kwargs["reason"] == "Error en ciudad"
    assert repository.updated_kwargs["changed_fields"] == ["city"]
    assert repository.updated_kwargs["action"] == "student_update"


async def test_student_cancel_records_student_cancel_action() -> None:
    service, repository = _service(_internship())

    result = await service.cancel_by_student(
        internship_id=7,
        actor=_user(),
        reason="  Me equivoque de empresa  ",
    )

    assert result.is_cancelled is True
    assert result.blocks_new_registration is False
    assert repository.cancelled_kwargs["actor_id"] == 10
    assert repository.cancelled_kwargs["reason"] == "Me equivoque de empresa"
    assert repository.cancelled_kwargs["action"] == "student_cancel"


async def test_student_update_rejects_non_owner() -> None:
    service, repository = _service(_internship(user_id=99))
    payload = StudentInternshipUpdateRequest(reason="Correccion", city="Temuco")

    with pytest.raises(HTTPException) as exc_info:
        await service.update_student_fields(
            internship_id=7,
            actor=_user(user_id=10),
            payload=payload,
        )

    assert exc_info.value.status_code == 403
    assert repository.updated_kwargs is None


async def test_student_update_rejects_expired_window() -> None:
    service, repository = _service(_internship(hours_old=25))
    payload = StudentInternshipUpdateRequest(reason="Correccion", city="Temuco")

    with pytest.raises(HTTPException) as exc_info:
        await service.update_student_fields(
            internship_id=7,
            actor=_user(),
            payload=payload,
        )

    assert exc_info.value.status_code == 409
    assert "window_expired" in exc_info.value.detail["reasons"]
    assert repository.updated_kwargs is None


async def test_student_update_rejects_non_pending_status() -> None:
    service, repository = _service(_internship(status_title="Aprobada"))
    payload = StudentInternshipUpdateRequest(reason="Correccion", city="Temuco")

    with pytest.raises(HTTPException) as exc_info:
        await service.update_student_fields(
            internship_id=7,
            actor=_user(),
            payload=payload,
        )

    assert exc_info.value.status_code == 409
    assert "status_not_pending" in exc_info.value.detail["reasons"]
    assert repository.updated_kwargs is None


async def test_student_update_rejects_after_administrative_action() -> None:
    service, repository = _service(
        _internship(),
        history=[_history(), _history("admin_update")],
    )
    payload = StudentInternshipUpdateRequest(reason="Correccion", city="Temuco")

    with pytest.raises(HTTPException) as exc_info:
        await service.update_student_fields(
            internship_id=7,
            actor=_user(),
            payload=payload,
        )

    assert exc_info.value.status_code == 409
    assert "administrative_action_exists" in exc_info.value.detail["reasons"]
    assert repository.updated_kwargs is None


async def test_student_update_rejects_blank_reason() -> None:
    service, repository = _service(_internship())
    payload = StudentInternshipUpdateRequest(reason="   ", city="Temuco")

    with pytest.raises(HTTPException) as exc_info:
        await service.update_student_fields(
            internship_id=7,
            actor=_user(),
            payload=payload,
        )

    assert exc_info.value.status_code == 400
    assert repository.updated_kwargs is None
