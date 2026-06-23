"""Tests para duplicidad de solicitudes por estudiante y tipo de practica."""

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.internships.models.internship_model import PracticeTypeEnum
from app.modules.internships.schemas.internship_schema import InternshipCreateRequest
from app.modules.internships.services.internship_service import InternshipService


def _state(title: str = "Pendiente", state_id: int = 1) -> SimpleNamespace:
    return SimpleNamespace(id=state_id, title=title)


def _blocking_internship(
    internship_id: int = 44,
    internship_type: PracticeTypeEnum = PracticeTypeEnum.practice_1,
    status_title: str = "Pendiente",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=internship_id,
        internship_type=internship_type,
        status=_state(status_title),
        blocks_new_registration=True,
    )


def _create_payload(
    internship_type: PracticeTypeEnum = PracticeTypeEnum.practice_1,
) -> InternshipCreateRequest:
    return InternshipCreateRequest(
        org_name="Empresa",
        sector="Tecnologia",
        address="Av. Siempre Viva 123",
        city="Temuco",
        org_phone="+56911111111",
        web="https://empresa.example",
        supervisor_name="Ana Perez",
        supervisor_profession="Ingeniera",
        supervisor_position="Jefa",
        supervisor_department="TI",
        supervisor_email="ana.perez@empresa.example",
        supervisor_phone="+56922222222",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 1),
        schedule="09:00 - 18:00",
        days="Lunes a viernes",
        modality="Presencial",
        internship_address="Av. Practica 456",
        act_description="Desarrollo de software",
        ben_description="Bono locomocion",
        amount=0,
        internship_period="Semestre",
        internship_type=internship_type,
    )


class FakeDuplicateRepository:
    def __init__(
        self,
        blocking_internship: SimpleNamespace | None = None,
    ) -> None:
        self.blocking_internship = blocking_internship
        self.created = None

    async def get_state_by_title(self, title: str):
        return _state(title)

    async def get_student_requirement(self, **kwargs):
        if kwargs.get("requirement") == "induction":
            return SimpleNamespace(is_completed=True)
        return None

    async def is_internship_applications_disabled(self) -> bool:
        return False

    async def get_blocking_internship_for_registration(self, **kwargs):
        return self.blocking_internship

    async def create_internship_with_history(self, **kwargs):
        self.created = kwargs["internship"]
        self.created.id = 99
        self.created.status_id = kwargs["initial_status"].id
        return self.created

    async def list_internships_by_user(self, user_id: int):
        return []

    async def get_passed_induction_attempt(self, user_id: int):
        return None

    async def get_active_induction_content(self):
        return None


def _service(repository: FakeDuplicateRepository) -> InternshipService:
    return InternshipService(internship_repository=repository)


async def test_create_internship_rejects_blocking_same_type() -> None:
    repository = FakeDuplicateRepository(blocking_internship=_blocking_internship())
    service = _service(repository)

    with pytest.raises(HTTPException) as exc_info:
        await service.create_internship(
            internship_data=_create_payload(),
            user_id=10,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "duplicate_internship_type"
    assert exc_info.value.detail["existing_internship_id"] == 44
    assert exc_info.value.detail["internship_type"] == "Práctica de Estudio I"
    assert exc_info.value.detail["existing_status"] == "Pendiente"
    assert repository.created is None


async def test_create_internship_marks_new_request_as_blocking() -> None:
    repository = FakeDuplicateRepository()
    service = _service(repository)

    result = await service.create_internship(
        internship_data=_create_payload(),
        user_id=10,
    )

    assert result.id == 99
    assert result.blocks_new_registration is True


async def test_registration_eligibility_reports_blocking_internship() -> None:
    repository = FakeDuplicateRepository(
        blocking_internship=_blocking_internship(status_title="Aprobada"),
    )
    service = _service(repository)

    result = await service.get_registration_eligibility(
        user_id=10,
        internship_type=PracticeTypeEnum.practice_1,
    )

    assert result.has_blocking_internship is True
    assert result.blocking_internship_id == 44
    assert result.blocking_internship_status == "Aprobada"
    assert result.can_create_request is False
    assert result.blocked is True
