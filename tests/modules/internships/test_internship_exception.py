"""Tests unitarios para excepciones administrativas de practicas."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.internships.services.internship_service import InternshipService


def _status(status_id: int, title: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=status_id,
        title=title,
        description=f"Estado {title}",
    )


def _user(
    user_id: int,
    first_name: str,
    last_name: str,
    roles: list[str] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        email=f"{first_name.lower()}.{last_name.lower()}@ufro.cl",
        first_name=first_name,
        last_name=last_name,
        roles=[
            SimpleNamespace(role=SimpleNamespace(name=role_name))
            for role_name in (roles or [])
        ],
    )


class FakeInternshipRepository:
    def __init__(self) -> None:
        self.internship_by_id = None
        self.created_exception_rule = None
        self.created_exception_reason = None
        self.created_exception_authorized_by = None
        self.exception_by_rule = None
        self._exceptions_by_rule = {}
        self.updated_insurance_status = None
        self.updated_insurance_actor_id = None
        self.updated_insurance_notes = None

    async def get_internship_by_id(self, internship_id: int):
        return self.internship_by_id

    async def get_exception_by_rule(self, internship_id: int, rule: str):
        dict_value = self._exceptions_by_rule.get((internship_id, rule))
        if dict_value is not None:
            return dict_value
        return self.exception_by_rule

    async def create_exception(
        self,
        internship_id: int,
        rule: str,
        reason: str,
        authorized_by: int,
    ):
        self.created_exception_rule = rule
        self.created_exception_reason = reason
        self.created_exception_authorized_by = authorized_by

        return SimpleNamespace(
            id=1,
            internship_id=internship_id,
            rule=rule,
            reason=reason,
            authorized_by=authorized_by,
            actor=_user(
                authorized_by,
                "Ana",
                "Director",
                roles=["Director de carrera"],
            ),
        )

    async def update_school_insurance_validation(
        self,
        internship,
        status,
        actor_id,
        notes=None,
    ):
        internship.insurance_status = status
        internship.insurance_validated_by = actor_id
        internship.insurance_notes = notes
        self.updated_insurance_status = status
        self.updated_insurance_actor_id = actor_id
        self.updated_insurance_notes = notes
        return internship


def _repository_with_pending_internship() -> FakeInternshipRepository:
    repository = FakeInternshipRepository()
    repository.internship_by_id = SimpleNamespace(
        id=7,
        status_id=1,
        status=_status(1, "Pendiente"),
    )
    return repository


@pytest.mark.asyncio
async def test_grant_exception_success_and_idempotency() -> None:
    repository = _repository_with_pending_internship()
    service = InternshipService(internship_repository=repository)
    actor = _user(
        user_id=22,
        first_name="Ana",
        last_name="Director",
        roles=["Director de carrera"],
    )

    exception = await service.grant_exception(
        internship_id=7,
        actor=actor,
        rule="school_insurance",
        reason="Poliza fisica en proceso de firma por el Director de Finanzas.",
    )

    assert exception.internship_id == 7
    assert repository.created_exception_rule == "school_insurance"
    assert repository.created_exception_authorized_by == 22
    assert str(repository.updated_insurance_status.value) == "exception_authorized"
    assert repository.updated_insurance_actor_id == 22

    repository.exception_by_rule = exception
    second_call_exception = await service.grant_exception(
        internship_id=7,
        actor=actor,
        rule="school_insurance",
        reason="Razon alternativa no procesada.",
    )

    assert second_call_exception is exception


@pytest.mark.asyncio
async def test_grant_exception_rejects_invalid_rules() -> None:
    repository = _repository_with_pending_internship()
    service = InternshipService(internship_repository=repository)
    actor = _user(
        user_id=22,
        first_name="Ana",
        last_name="Director",
        roles=["Director de carrera"],
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.grant_exception(
            internship_id=7,
            actor=actor,
            rule="invalid_rule_name",
            reason="Prueba de fallo.",
        )

    assert exc_info.value.status_code == 400
    assert "no admite excepción administrativa" in exc_info.value.detail


@pytest.mark.asyncio
async def test_grant_exception_requires_privileged_role() -> None:
    repository = _repository_with_pending_internship()
    service = InternshipService(internship_repository=repository)
    student_actor = _user(
        user_id=10,
        first_name="Cami",
        last_name="Rojas",
        roles=["Estudiante"],
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.grant_exception(
            internship_id=7,
            actor=student_actor,
            rule="school_insurance",
            reason="Intento omitir la validacion de manera autonoma.",
        )

    assert exc_info.value.status_code == 403
    assert "Insufficient permissions" in exc_info.value.detail


@pytest.mark.asyncio
async def test_grant_sequentiality_exception_success() -> None:
    repository = _repository_with_pending_internship()
    service = InternshipService(internship_repository=repository)
    actor = _user(
        user_id=22,
        first_name="Juan",
        last_name="Coordinador",
        roles=["Encargado de practica"],
    )

    exception = await service.grant_exception(
        internship_id=7,
        actor=actor,
        rule="sequentiality",
        reason="El estudiante curso Practica I en otra institucion.",
    )

    assert exception.internship_id == 7
    assert repository.created_exception_rule == "sequentiality"
    assert repository.created_exception_authorized_by == 22
