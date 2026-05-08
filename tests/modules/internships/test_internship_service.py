from datetime import date

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
        start_date=date(2026, 6, 1),
        end_date=date(2026, 8, 31),
        schedule="09:00-18:00",
        days="Lunes a viernes",
        modality="Presencial",
        internship_address="Av. Practica 456",
        act_description="Desarrollo de funcionalidades backend.",
        ben_description="Apoyo al equipo de plataforma.",
        amount=120000,
    )


class FakeInternshipRepository:
    def __init__(self) -> None:
        self.created_internship = None
        self.requested_internship_id = None
        self.requested_user_id = None
        self.internship_by_id = None
        self.internships_by_user = []

    async def create_internship(self, internship):
        self.created_internship = internship

        return internship

    async def get_internship_by_id(self, internship_id: int):
        self.requested_internship_id = internship_id

        return self.internship_by_id

    async def list_internships_by_user(self, user_id: int):
        self.requested_user_id = user_id

        return self.internships_by_user


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
