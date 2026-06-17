"""Controlador HTTP para agenda y reservas de entrevistas."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.database import get_db
from app.modules.auth.dependencies.auth_dependency import get_current_user
from app.modules.auth.models.user_model import User
from app.modules.scheduling.models.presentation_model import PresentationPurposeEnum
from app.modules.scheduling.repositories.scheduling_repository import (
    SchedulingRepository,
)
from app.modules.scheduling.schemas.scheduling_schema import (
    AppointmentCancelRequest,
    AppointmentRescheduleRequest,
    AvailabilityCreateRequest,
    AvailabilityUpdateRequest,
    PresentationSlotResponse,
    SlotReserveRequest,
)
from app.modules.scheduling.services.scheduling_service import SchedulingService


router = APIRouter(prefix="/scheduling", tags=["Scheduling"])


def _build_service(db: AsyncSession) -> SchedulingService:
    return SchedulingService(repository=SchedulingRepository(db))


@router.post(
    "/availability",
    response_model=list[PresentationSlotResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_availability(
    payload: AvailabilityCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[PresentationSlotResponse]:
    """Publica bloques de disponibilidad para entrevistas o presentaciones."""

    service = _build_service(db)
    slots = await service.create_availability(actor=current_user, payload=payload)

    return [PresentationSlotResponse.model_validate(slot) for slot in slots]


@router.put("/availability/{slot_id}", response_model=PresentationSlotResponse)
async def update_availability(
    slot_id: int,
    payload: AvailabilityUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PresentationSlotResponse:
    """Edita un bloque futuro de disponibilidad."""

    service = _build_service(db)
    slot = await service.update_availability(
        slot_id=slot_id,
        actor=current_user,
        payload=payload,
    )

    return PresentationSlotResponse.model_validate(slot)


@router.get("/slots", response_model=list[PresentationSlotResponse])
async def list_available_slots(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    purpose: Annotated[PresentationPurposeEnum | None, Query()] = None,
) -> list[PresentationSlotResponse]:
    """Lista bloques disponibles publicados."""

    service = _build_service(db)
    slots = await service.list_available_slots(
        date_from=date_from,
        date_to=date_to,
        purpose=purpose,
    )

    return [PresentationSlotResponse.model_validate(slot) for slot in slots]


@router.get("/appointments", response_model=list[PresentationSlotResponse])
async def list_my_appointments(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[PresentationSlotResponse]:
    """Lista citas agendadas visibles para el usuario autenticado."""

    service = _build_service(db)
    slots = await service.list_my_appointments(actor=current_user)

    return [PresentationSlotResponse.model_validate(slot) for slot in slots]


@router.post("/slots/{slot_id}/reserve", response_model=PresentationSlotResponse)
async def reserve_slot(
    slot_id: int,
    payload: SlotReserveRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PresentationSlotResponse:
    """Reserva un bloque disponible para una practica del estudiante."""

    service = _build_service(db)
    slot = await service.reserve_slot(
        slot_id=slot_id,
        actor=current_user,
        payload=payload,
    )

    return PresentationSlotResponse.model_validate(slot)


@router.post(
    "/appointments/{appointment_id}/cancel",
    response_model=PresentationSlotResponse,
)
async def cancel_appointment(
    appointment_id: int,
    payload: AppointmentCancelRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PresentationSlotResponse:
    """Cancela una cita agendada."""

    service = _build_service(db)
    slot = await service.cancel_appointment(
        appointment_id=appointment_id,
        actor=current_user,
        payload=payload,
    )

    return PresentationSlotResponse.model_validate(slot)


@router.post(
    "/appointments/{appointment_id}/reschedule",
    response_model=PresentationSlotResponse,
)
async def reschedule_appointment(
    appointment_id: int,
    payload: AppointmentRescheduleRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PresentationSlotResponse:
    """Reprograma una cita a otro bloque disponible."""

    service = _build_service(db)
    slot = await service.reschedule_appointment(
        appointment_id=appointment_id,
        actor=current_user,
        payload=payload,
    )

    return PresentationSlotResponse.model_validate(slot)


@router.post(
    "/availability/{slot_id}/close",
    response_model=PresentationSlotResponse,
)
async def close_availability(
    slot_id: int,
    payload: AppointmentCancelRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PresentationSlotResponse:
    """Cierra un bloque disponible antes de que sea reservado."""

    service = _build_service(db)
    slot = await service.close_availability(
        slot_id=slot_id,
        actor=current_user,
        payload=payload,
    )

    return PresentationSlotResponse.model_validate(slot)


@router.delete(
    "/availability/{slot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_availability(
    slot_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Elimina un bloque futuro de disponibilidad."""

    service = _build_service(db)
    await service.delete_availability(slot_id=slot_id, actor=current_user)
