"""Tests para edición administrativa y anulación lógica de prácticas."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.internships.schemas.internship_schema import (
    InternshipAdminUpdateRequest,
)
from app.modules.internships.services.internship_service import (
    APPROVED_STATUS_TITLE,
    PENDING_STATUS_TITLE,
    InternshipService,
)


def _make_state(title: str, state_id: int = 1) -> MagicMock:
    state = MagicMock()
    state.id = state_id
    state.title = title
    return state


def _make_internship(
    status_title: str | None,
    internship_id: int = 1,
    is_cancelled: bool = False,
) -> MagicMock:
    internship = MagicMock()
    internship.id = internship_id
    internship.status_id = 1
    internship.status = _make_state(status_title) if status_title else None
    internship.is_cancelled = is_cancelled
    internship.blocks_new_registration = True
    internship.start_date = date(2026, 1, 1)
    internship.end_date = date(2026, 2, 1)
    return internship


def _make_user(*role_names: str) -> MagicMock:
    user = MagicMock()
    user.id = 99
    user.roles = [
        SimpleNamespace(role=SimpleNamespace(name=name))
        for name in role_names
    ]
    return user


def _make_service(internship: MagicMock | None) -> tuple[InternshipService, AsyncMock]:
    repo = AsyncMock()
    repo.get_internship_by_id.return_value = internship

    async def _update_admin_fields(**kwargs):
        for field_name, value in kwargs["updates"].items():
            setattr(kwargs["internship"], field_name, value)
        return kwargs["internship"]

    async def _cancel_with_history(**kwargs):
        internship = kwargs["internship"]
        internship.is_cancelled = True
        internship.cancelled_by = kwargs["actor_id"]
        internship.cancellation_reason = kwargs["reason"]
        internship.blocks_new_registration = False
        return internship

    repo.update_internship_admin_fields_with_history.side_effect = (
        _update_admin_fields
    )
    repo.cancel_internship_with_history.side_effect = _cancel_with_history
    return InternshipService(internship_repository=repo), repo


class TestAdminUpdate:
    @pytest.mark.asyncio
    async def test_admin_update_valid_updates_allowed_fields(self) -> None:
        internship = _make_internship(PENDING_STATUS_TITLE)
        service, repo = _make_service(internship)
        actor = _make_user("Encargado de practica")
        payload = InternshipAdminUpdateRequest(
            reason="  Corrección de datos de contacto  ",
            city="Temuco",
            supervisor_phone="+56912345678",
        )

        result = await service.update_admin_fields(
            internship_id=internship.id,
            actor=actor,
            payload=payload,
        )

        assert result.city == "Temuco"
        assert result.supervisor_phone == "+56912345678"
        repo.update_internship_admin_fields_with_history.assert_awaited_once()
        call_kwargs = repo.update_internship_admin_fields_with_history.call_args.kwargs
        assert call_kwargs["updates"] == {
            "city": "Temuco",
            "supervisor_phone": "+56912345678",
        }
        assert call_kwargs["changed_fields"] == ["city", "supervisor_phone"]
        assert call_kwargs["actor_id"] == actor.id
        assert call_kwargs["reason"] == "Corrección de datos de contacto"

    def test_admin_update_rejects_forbidden_field(self) -> None:
        with pytest.raises(ValidationError):
            InternshipAdminUpdateRequest(
                reason="Corrección",
                has_school_insurance=True,
            )

    @pytest.mark.asyncio
    async def test_admin_update_rejects_wrong_role(self) -> None:
        internship = _make_internship(PENDING_STATUS_TITLE)
        service, repo = _make_service(internship)
        actor = _make_user("Secretaria de Carrera")
        payload = InternshipAdminUpdateRequest(reason="Corrección", city="Temuco")

        with pytest.raises(HTTPException) as exc_info:
            await service.update_admin_fields(
                internship_id=internship.id,
                actor=actor,
                payload=payload,
            )

        assert exc_info.value.status_code == 403
        repo.update_internship_admin_fields_with_history.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_admin_update_rejects_terminal_status(self) -> None:
        internship = _make_internship(APPROVED_STATUS_TITLE)
        service, repo = _make_service(internship)
        actor = _make_user("Director de carrera")
        payload = InternshipAdminUpdateRequest(reason="Corrección", city="Temuco")

        with pytest.raises(HTTPException) as exc_info:
            await service.update_admin_fields(
                internship_id=internship.id,
                actor=actor,
                payload=payload,
            )

        assert exc_info.value.status_code == 409
        repo.update_internship_admin_fields_with_history.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_admin_update_rejects_blank_reason(self) -> None:
        internship = _make_internship(PENDING_STATUS_TITLE)
        service, repo = _make_service(internship)
        actor = _make_user("Encargado de practica")
        payload = InternshipAdminUpdateRequest(reason="   ", city="Temuco")

        with pytest.raises(HTTPException) as exc_info:
            await service.update_admin_fields(
                internship_id=internship.id,
                actor=actor,
                payload=payload,
            )

        assert exc_info.value.status_code == 400
        repo.update_internship_admin_fields_with_history.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_admin_update_rejects_without_editable_fields(self) -> None:
        internship = _make_internship(PENDING_STATUS_TITLE)
        service, repo = _make_service(internship)
        actor = _make_user("Director de carrera")
        payload = InternshipAdminUpdateRequest(reason="Corrección")

        with pytest.raises(HTTPException) as exc_info:
            await service.update_admin_fields(
                internship_id=internship.id,
                actor=actor,
                payload=payload,
            )

        assert exc_info.value.status_code == 400
        repo.update_internship_admin_fields_with_history.assert_not_awaited()


class TestCancelInternship:
    @pytest.mark.asyncio
    async def test_cancel_valid_marks_internship_cancelled(self) -> None:
        internship = _make_internship(PENDING_STATUS_TITLE)
        service, repo = _make_service(internship)
        actor = _make_user("Director de carrera")

        result = await service.cancel(
            internship_id=internship.id,
            actor=actor,
            reason="  Solicitud duplicada  ",
        )

        assert result.is_cancelled is True
        assert result.blocks_new_registration is False
        assert result.cancelled_by == actor.id
        assert result.cancellation_reason == "Solicitud duplicada"
        repo.cancel_internship_with_history.assert_awaited_once()
        call_kwargs = repo.cancel_internship_with_history.call_args.kwargs
        assert call_kwargs["actor_id"] == actor.id
        assert call_kwargs["reason"] == "Solicitud duplicada"

    @pytest.mark.asyncio
    async def test_cancel_missing_internship_returns_404(self) -> None:
        service, repo = _make_service(internship=None)
        actor = _make_user("Encargado de practica")

        with pytest.raises(HTTPException) as exc_info:
            await service.cancel(
                internship_id=999,
                actor=actor,
                reason="Solicitud duplicada",
            )

        assert exc_info.value.status_code == 404
        repo.cancel_internship_with_history.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cancel_rejects_already_cancelled_internship(self) -> None:
        internship = _make_internship(PENDING_STATUS_TITLE, is_cancelled=True)
        service, repo = _make_service(internship)
        actor = _make_user("Director de carrera")

        with pytest.raises(HTTPException) as exc_info:
            await service.cancel(
                internship_id=internship.id,
                actor=actor,
                reason="Solicitud duplicada",
            )

        assert exc_info.value.status_code == 409
        repo.cancel_internship_with_history.assert_not_awaited()
