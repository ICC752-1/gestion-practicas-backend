"""Repositorio de plantillas y cartas de presentacion."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.presentation_letters.models.presentation_letter_model import (
    PresentationLetter,
    PresentationLetterTemplate,
)


class PresentationLetterRepository:
    """Encapsula consultas y persistencia del modulo de cartas."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_templates(self) -> list[PresentationLetterTemplate]:
        query = (
            select(PresentationLetterTemplate)
            .where(PresentationLetterTemplate.is_active.is_(True))
            .order_by(PresentationLetterTemplate.practice_type)
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def get_active_template(
        self,
        practice_type: str,
    ) -> PresentationLetterTemplate | None:
        query = select(PresentationLetterTemplate).where(
            PresentationLetterTemplate.practice_type == practice_type,
            PresentationLetterTemplate.is_active.is_(True),
        )
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def save_template(
        self,
        template: PresentationLetterTemplate,
    ) -> PresentationLetterTemplate:
        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)

        return template

    async def create_letter(self, letter: PresentationLetter) -> PresentationLetter:
        self.db.add(letter)
        await self.db.commit()
        await self.db.refresh(letter)

        loaded = await self.get_letter_by_id(letter.id)
        return loaded or letter

    async def save_letter(self, letter: PresentationLetter) -> PresentationLetter:
        await self.db.commit()
        await self.db.refresh(letter)

        loaded = await self.get_letter_by_id(letter.id)
        return loaded or letter

    async def get_letter_by_id(self, letter_id: int) -> PresentationLetter | None:
        query = (
            select(PresentationLetter)
            .where(PresentationLetter.id == letter_id)
            .options(
                selectinload(PresentationLetter.student),
                selectinload(PresentationLetter.template),
            )
        )
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def list_letters_for_student(
        self,
        student_id: int,
    ) -> list[PresentationLetter]:
        query = (
            select(PresentationLetter)
            .where(PresentationLetter.student_id == student_id)
            .options(
                selectinload(PresentationLetter.student),
                selectinload(PresentationLetter.template),
            )
            .order_by(PresentationLetter.created_at.desc())
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())
