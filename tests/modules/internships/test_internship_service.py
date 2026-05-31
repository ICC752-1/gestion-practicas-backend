from datetime import date, datetime
from types import SimpleNamespace

from app.modules.internships.models.internship_model import (
    PracticePeriodEnum,
    PracticeTypeEnum,
)
from app.modules.internships.schemas.internship_schema import InternshipCreateRequest
from app.modules.internships.services.internship_service import InternshipService


def _valid_payload() -> InternshipCreateRequest:
    return InternshipCreateRequest(
        org_name="Acme Chile",
        sector="Tecnologia",
        address="Av. Siempre Viva 123",
        city="Temuco",
        org_phone="+56912345678",
        web="https://acme.example",
        supervisor_name="Ana Perez",
        supervisor_profession="Ingeniera Civil Informatica",
        supervisor_position="Jefa de Proyectos",
        supervisor_department="Tecnologia",
        supervisor_email="ana.perez@acme.example",
        supervisor_phone="+56987654321",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 8, 31),
        schedule="09:00-18:00",
        days="Lunes a viernes",
        modality="Presencial",
        internship_address="Av. Practica 456",
        act_description="Desarrollo de funcionalidades backend.",
        ben_description="Apoyo al equipo de plataforma.",
        amount=120000,
        internship_period=PracticePeriodEnum.semester,
        internship_type=PracticeTypeEnum.practice_1,
        has_school_insurance=False,
    )


class FakeInternshipRepository:
    def __init__(self) -> None:
        self.created_internship = None
        self.requested_internship_id = None
        self.requested_user_id = None
        self.internship_by_id = None
        self.internships_by_user = []
        self.dashboard_internships = []

    async def create_internship(self, internship):
        self.created_internship = internship

        return internship

    async def get_internship_by_id(self, internship_id: int):
        self.requested_internship_id = internship_id

        return self.internship_by_id

    async def list_internships_by_user(self, user_id: int):
        self.requested_user_id = user_id

        return self.internships_by_user

    async def list_dashboard_internships(self):
        return self.dashboard_internships


def _student() -> SimpleNamespace:
    return SimpleNamespace(
        id=10,
        email="camila.rojas@ufromail.cl",
        first_name="Camila",
        last_name="Rojas",
        rut="11.111.111-1",
        degree="Ingenieria Civil Informatica",
    )


def _status(title: str) -> SimpleNamespace:
    return SimpleNamespace(title=title)


def _dashboard_internship(
    internship_id: int,
    status=None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=internship_id,
        org_name="Acme Chile",
        city="Temuco",
        internship_type=PracticeTypeEnum.practice_1,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 8, 31),
        upload_date=datetime(2026, 5, 29, 12, 0, 0),
        status=status,
        student=_student(),
    )


async def test_create_internship_assigns_authenticated_user_id() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)

    internship = await service.create_internship(
        internship_data=_valid_payload(),
        user_id=42,
    )

    assert internship is repository.created_internship
    assert internship.user_id == 42
    assert internship.org_name == "Acme Chile"
    assert internship.supervisor_email == "ana.perez@acme.example"


async def test_get_internship_delegates_lookup_to_repository() -> None:
    repository = FakeInternshipRepository()
    repository.internship_by_id = object()
    service = InternshipService(internship_repository=repository)

    internship = await service.get_internship(internship_id=7)

    assert internship is repository.internship_by_id
    assert repository.requested_internship_id == 7


async def test_list_user_internships_delegates_lookup_to_repository() -> None:
    repository = FakeInternshipRepository()
    repository.internships_by_user = [object(), object()]
    service = InternshipService(internship_repository=repository)

    internships = await service.list_user_internships(user_id=42)

    assert internships == repository.internships_by_user
    assert repository.requested_user_id == 42


async def test_list_dashboard_internships_maps_null_status_as_submitted() -> None:
    repository = FakeInternshipRepository()
    repository.dashboard_internships = [_dashboard_internship(1, status=None)]
    service = InternshipService(internship_repository=repository)

    internships = await service.list_dashboard_internships()

    assert len(internships) == 1
    assert internships[0].id == 1
    assert internships[0].status == "submitted"
    assert internships[0].status_label == "Pendiente"
    assert internships[0].student is not None
    assert internships[0].student.email == "camila.rojas@ufromail.cl"


async def test_list_dashboard_internships_filters_by_normalized_status() -> None:
    repository = FakeInternshipRepository()
    repository.dashboard_internships = [
        _dashboard_internship(1, status=_status("Reprobada")),
        _dashboard_internship(2, status=_status("Aprobada")),
        _dashboard_internship(3, status=_status("Rechazada")),
    ]
    service = InternshipService(internship_repository=repository)

    internships = await service.list_dashboard_internships(status_filter="rejected")

    assert [internship.id for internship in internships] == [1, 3]
    assert all(internship.status == "rejected" for internship in internships)


async def test_get_dashboard_stats_counts_normalized_statuses() -> None:
    repository = FakeInternshipRepository()
    repository.dashboard_internships = [
        _dashboard_internship(1, status=None),
        _dashboard_internship(2, status=_status("Pendiente")),
        _dashboard_internship(3, status=_status("En revisión")),
        _dashboard_internship(4, status=_status("Aprobada")),
        _dashboard_internship(5, status=_status("Rechazada")),
        _dashboard_internship(6, status=_status("Reprobada")),
    ]
    service = InternshipService(internship_repository=repository)

    stats = await service.get_dashboard_stats()

    assert stats.total == 6
    assert stats.submitted == 2
    assert stats.in_review == 1
    assert stats.approved == 1
    assert stats.rejected == 2
