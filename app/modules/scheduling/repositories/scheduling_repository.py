"""Repositorio de agenda para bloques de entrevistas y presentaciones."""

from datetime import date, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.internships.models.internship_model import Internship
from app.modules.scheduling.models.presentation_model import (
    Presentation,
    PresentationPurposeEnum,
    PresentationStatusEnum,
)


ACTIVE_BLOCK_STATUSES = (
    PresentationStatusEnum.available,
    PresentationStatusEnum.scheduled,
    PresentationStatusEnum.completed,
    PresentationStatusEnum.no_show,
)


class SchedulingRepository:
    """Encapsula lecturas y escrituras de agenda."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_slots(self, slots: list[Presentation]) -> list[Presentation]:
        """Persiste una lista de bloques de disponibilidad."""

        self.db.add_all(slots)
        await self.db.commit()

        for slot in slots:
            await self.db.refresh(slot)

        return slots

    async def save_slot(self, slot: Presentation) -> Presentation:
        """Confirma los cambios de un bloque existente."""

        await self.db.commit()
        await self.db.refresh(slot)

        return slot

    async def save_slots(self, slots: list[Presentation]) -> list[Presentation]:
        """Confirma cambios de varios bloques en una misma transaccion."""

        await self.db.commit()

        for slot in slots:
            await self.db.refresh(slot)

        return slots

    async def get_slot_by_id(self, slot_id: int) -> Presentation | None:
        """Obtiene un bloque por identificador."""

        query = (
            select(Presentation)
            .where(Presentation.id == slot_id)
            .options(
                selectinload(Presentation.internship),
                selectinload(Presentation.student),
                selectinload(Presentation.owner),
            )
        )
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def get_slot_by_id_for_update(self, slot_id: int) -> Presentation | None:
        """Obtiene un bloque con bloqueo de fila para evitar dobles reservas."""

        query = (
            select(Presentation)
            .where(Presentation.id == slot_id)
            .with_for_update()
            .options(
                selectinload(Presentation.internship),
                selectinload(Presentation.student),
                selectinload(Presentation.owner),
            )
        )
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def get_internship_by_id(self, internship_id: int) -> Internship | None:
        """Obtiene una practica por identificador."""

        query = select(Internship).where(Internship.id == internship_id)
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def list_available_slots(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        purpose: PresentationPurposeEnum | None = None,
    ) -> list[Presentation]:
        """Lista bloques publicados disponibles."""

        query = select(Presentation).where(
            Presentation.status == PresentationStatusEnum.available,
        )

        if date_from is not None:
            query = query.where(Presentation.date >= date_from)

        if date_to is not None:
            query = query.where(Presentation.date <= date_to)

        if purpose is not None:
            query = query.where(Presentation.purpose == purpose)

        query = query.order_by(Presentation.date.asc(), Presentation.start_time.asc())
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def list_appointments_for_owner(self, owner_id: int) -> list[Presentation]:
        """Lista citas agendadas con un administrativo especifico."""

        query = (
            select(Presentation)
            .where(
                Presentation.owner_id == owner_id,
                Presentation.status == PresentationStatusEnum.scheduled,
            )
            .options(
                selectinload(Presentation.internship),
                selectinload(Presentation.student),
            )
            .order_by(Presentation.date.asc(), Presentation.start_time.asc())
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def list_appointments_for_student(self, user_id: int) -> list[Presentation]:
        """Lista citas agendadas por un estudiante."""

        query = (
            select(Presentation)
            .where(
                Presentation.user_id == user_id,
                Presentation.status == PresentationStatusEnum.scheduled,
            )
            .options(
                selectinload(Presentation.internship),
                selectinload(Presentation.owner),
            )
            .order_by(Presentation.date.asc(), Presentation.start_time.asc())
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def has_owner_overlap(
        self,
        owner_id: int,
        slot_date: date,
        start_time: time,
        end_time: time,
        exclude_slot_id: int | None = None,
    ) -> bool:
        """Indica si el administrativo ya tiene un bloque solapado."""

        query = select(Presentation.id).where(
            Presentation.owner_id == owner_id,
            Presentation.date == slot_date,
            Presentation.status.in_(ACTIVE_BLOCK_STATUSES),
            Presentation.start_time < end_time,
            Presentation.end_time > start_time,
        )

        if exclude_slot_id is not None:
            query = query.where(Presentation.id != exclude_slot_id)

        result = await self.db.execute(query.limit(1))

        return result.scalar_one_or_none() is not None

    async def has_student_overlap(
        self,
        user_id: int,
        slot_date: date,
        start_time: time,
        end_time: time,
        exclude_slot_id: int | None = None,
    ) -> bool:
        """Indica si el estudiante ya tiene una cita solapada."""

        query = select(Presentation.id).where(
            Presentation.user_id == user_id,
            Presentation.date == slot_date,
            Presentation.status == PresentationStatusEnum.scheduled,
            Presentation.start_time < end_time,
            Presentation.end_time > start_time,
        )

        if exclude_slot_id is not None:
            query = query.where(Presentation.id != exclude_slot_id)

        result = await self.db.execute(query.limit(1))

        return result.scalar_one_or_none() is not None

    async def has_active_appointment_for_internship(
        self,
        internship_id: int,
        purpose: PresentationPurposeEnum,
    ) -> bool:
        """Indica si la practica ya tiene una cita vigente para ese proposito."""

        query = select(Presentation.id).where(
            Presentation.internship_id == internship_id,
            Presentation.purpose == purpose,
            Presentation.status == PresentationStatusEnum.scheduled,
        )
        result = await self.db.execute(query.limit(1))

        return result.scalar_one_or_none() is not None
