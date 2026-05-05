"""Data access repository for internships."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.internships.models.internship_model import Internship


class InternshipRepository:
    """Encapsulates persistence operations for internships."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_internship(self, internship: Internship) -> Internship:
        self.db.add(internship)
        await self.db.commit()
        await self.db.refresh(internship)

        return internship

    async def get_internship_by_id(self, internship_id: int) -> Internship | None:
        query = select(Internship).where(Internship.id == internship_id)
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def list_internships_by_user(self, user_id: int) -> list[Internship]:
        query = (
            select(Internship)
            .where(Internship.user_id == user_id)
            .order_by(Internship.upload_date.desc())
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())
