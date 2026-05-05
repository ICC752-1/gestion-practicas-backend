"""Business service for internships."""

from app.modules.internships.models.internship_model import Internship
from app.modules.internships.repositories.internship_repository import (
    InternshipRepository,
)
from app.modules.internships.schemas.internship_schema import InternshipCreateRequest


class InternshipService:
    """Coordinates internship use cases."""

    def __init__(self, internship_repository: InternshipRepository) -> None:
        self.internship_repository = internship_repository

    async def create_internship(
        self,
        internship_data: InternshipCreateRequest,
        user_id: int,
    ) -> Internship:
        internship = Internship(
            **internship_data.model_dump(),
            user_id=user_id,
        )

        return await self.internship_repository.create_internship(internship)

    async def get_internship(self, internship_id: int) -> Internship | None:
        return await self.internship_repository.get_internship_by_id(internship_id)

    async def list_user_internships(self, user_id: int) -> list[Internship]:
        return await self.internship_repository.list_internships_by_user(user_id)
