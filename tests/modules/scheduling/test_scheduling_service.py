from datetime import date, time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.scheduling.models.presentation_model import (
    PresentationPurposeEnum,
    PresentationStatusEnum,
)
from app.modules.scheduling.schemas.scheduling_schema import (
    AppointmentCancelRequest,
    AppointmentRescheduleRequest,
    AvailabilityCreateRequest,
    SlotReserveRequest,
)
from app.modules.scheduling.services.scheduling_service import SchedulingService


def _user(user_id: int, roles: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        roles=[
            SimpleNamespace(role=SimpleNamespace(name=role_name))
            for role_name in roles
        ],
    )


def _slot(
    status: PresentationStatusEnum = PresentationStatusEnum.available,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=20,
        date=date(2099, 1, 10),
        start_time=time(10, 0),
        end_time=time(10, 30),
        duration_minutes=30,
        modality="Presencial",
        purpose=PresentationPurposeEnum.initial_interview,
        status=status,
        result=None,
        location=None,
        timezone="America/Santiago",
        comments=None,
        cancel_reason=None,
        created_at=None,
        updated_at=None,
        reserved_at=None,
        cancelled_at=None,
        internship_id=None,
        user_id=None,
        owner_id=2,
    )


def _internship(
    internship_id: int = 7,
    user_id: int = 1,
    is_cancelled: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=internship_id,
        user_id=user_id,
        is_cancelled=is_cancelled,
    )


class FakeSchedulingRepository:
    def __init__(self) -> None:
        self.slot = _slot()
        self.new_slot = _slot()
        self.new_slot.id = 21
        self.new_slot.start_time = time(11, 0)
        self.new_slot.end_time = time(11, 30)
        self.internship = _internship()
        self.owner_overlap = False
        self.student_overlap = False
        self.duplicate_appointment = False
        self.created_slots = []
        self.saved_slot = None
        self.saved_slots = []

    async def create_slots(self, slots):
        self.created_slots = slots
        return slots

    async def save_slot(self, slot):
        self.saved_slot = slot
        return slot

    async def save_slots(self, slots):
        self.saved_slots = slots
        return slots

    async def get_slot_by_id_for_update(self, slot_id: int):
        if self.slot.id == slot_id:
            return self.slot

        if self.new_slot.id == slot_id:
            return self.new_slot

        return None

    async def get_internship_by_id(self, internship_id: int):
        return self.internship if self.internship.id == internship_id else None

    async def has_owner_overlap(
        self,
        owner_id: int,
        slot_date: date,
        start_time: time,
        end_time: time,
        exclude_slot_id: int | None = None,
    ) -> bool:
        return self.owner_overlap

    async def has_student_overlap(
        self,
        user_id: int,
        slot_date: date,
        start_time: time,
        end_time: time,
        exclude_slot_id: int | None = None,
    ) -> bool:
        return self.student_overlap

    async def has_active_appointment_for_internship(
        self,
        internship_id: int,
        purpose: PresentationPurposeEnum,
    ) -> bool:
        return self.duplicate_appointment


def _availability_payload() -> AvailabilityCreateRequest:
    return AvailabilityCreateRequest(
        date=date(2099, 1, 10),
        start_time=time(9, 0),
        end_time=time(10, 0),
        duration_minutes=30,
        modality="Presencial",
        purpose=PresentationPurposeEnum.initial_interview,
    )


async def test_create_availability_generates_expected_blocks() -> None:
    repository = FakeSchedulingRepository()
    service = SchedulingService(repository=repository)

    slots = await service.create_availability(
        actor=_user(2, ["Encargado de practica"]),
        payload=_availability_payload(),
    )

    assert len(slots) == 2
    assert slots[0].start_time == time(9, 0)
    assert slots[0].end_time == time(9, 30)
    assert slots[1].start_time == time(9, 30)
    assert slots[1].end_time == time(10, 0)
    assert all(slot.owner_id == 2 for slot in slots)


async def test_create_availability_rejects_non_admin_role() -> None:
    repository = FakeSchedulingRepository()
    service = SchedulingService(repository=repository)

    with pytest.raises(HTTPException) as exc_info:
        await service.create_availability(
            actor=_user(1, ["Estudiante"]),
            payload=_availability_payload(),
        )

    assert exc_info.value.status_code == 403


async def test_reserve_slot_assigns_student_and_internship() -> None:
    repository = FakeSchedulingRepository()
    service = SchedulingService(repository=repository)

    slot = await service.reserve_slot(
        slot_id=20,
        actor=_user(1, ["Estudiante"]),
        payload=SlotReserveRequest(internship_id=7),
    )

    assert slot.status == PresentationStatusEnum.scheduled
    assert slot.user_id == 1
    assert slot.internship_id == 7
    assert slot.reserved_at is not None
    assert repository.saved_slot is slot


async def test_reserve_slot_rejects_duplicate_appointment_for_internship() -> None:
    repository = FakeSchedulingRepository()
    repository.duplicate_appointment = True
    service = SchedulingService(repository=repository)

    with pytest.raises(HTTPException) as exc_info:
        await service.reserve_slot(
            slot_id=20,
            actor=_user(1, ["Estudiante"]),
            payload=SlotReserveRequest(internship_id=7),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == (
        "La practica ya tiene una cita agendada para este tipo"
    )


async def test_reserve_slot_rejects_cancelled_internship() -> None:
    repository = FakeSchedulingRepository()
    repository.internship = _internship(is_cancelled=True)
    service = SchedulingService(repository=repository)

    with pytest.raises(HTTPException) as exc_info:
        await service.reserve_slot(
            slot_id=20,
            actor=_user(1, ["Estudiante"]),
            payload=SlotReserveRequest(internship_id=7),
        )

    assert exc_info.value.status_code == 409


async def test_admin_cancel_requires_reason() -> None:
    repository = FakeSchedulingRepository()
    repository.slot = _slot(status=PresentationStatusEnum.scheduled)
    service = SchedulingService(repository=repository)

    with pytest.raises(HTTPException) as exc_info:
        await service.cancel_appointment(
            appointment_id=20,
            actor=_user(2, ["Encargado de practica"]),
            payload=AppointmentCancelRequest(),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "El motivo de cancelacion es obligatorio"


async def test_student_can_cancel_own_appointment_without_reason() -> None:
    repository = FakeSchedulingRepository()
    repository.slot = _slot(status=PresentationStatusEnum.scheduled)
    repository.slot.user_id = 1
    service = SchedulingService(repository=repository)

    slot = await service.cancel_appointment(
        appointment_id=20,
        actor=_user(1, ["Estudiante"]),
        payload=AppointmentCancelRequest(),
    )

    assert slot.status == PresentationStatusEnum.cancelled
    assert slot.cancelled_at is not None


async def test_student_can_reschedule_own_appointment() -> None:
    repository = FakeSchedulingRepository()
    repository.slot = _slot(status=PresentationStatusEnum.scheduled)
    repository.slot.user_id = 1
    repository.slot.internship_id = 7
    service = SchedulingService(repository=repository)

    slot = await service.reschedule_appointment(
        appointment_id=20,
        actor=_user(1, ["Estudiante"]),
        payload=AppointmentRescheduleRequest(new_slot_id=21),
    )

    assert repository.slot.status == PresentationStatusEnum.cancelled
    assert repository.slot.cancel_reason == "Reprogramacion de cita"
    assert slot.id == 21
    assert slot.status == PresentationStatusEnum.scheduled
    assert slot.user_id == 1
    assert slot.internship_id == 7


async def test_reschedule_rejects_slot_with_different_purpose() -> None:
    repository = FakeSchedulingRepository()
    repository.slot = _slot(status=PresentationStatusEnum.scheduled)
    repository.slot.user_id = 1
    repository.new_slot.purpose = PresentationPurposeEnum.final_presentation
    service = SchedulingService(repository=repository)

    with pytest.raises(HTTPException) as exc_info:
        await service.reschedule_appointment(
            appointment_id=20,
            actor=_user(1, ["Estudiante"]),
            payload=AppointmentRescheduleRequest(new_slot_id=21),
        )

    assert exc_info.value.status_code == 409
