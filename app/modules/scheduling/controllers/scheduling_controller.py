"""Controlador HTTP para agenda y reservas de entrevistas."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.database import get_db
from app.core.config import config
from app.modules.auth.dependencies.auth_dependency import get_current_user
from app.modules.auth.models.user_model import User
from app.modules.notifications.repositories.notification_repository import (
    NotificationRepository,
)
from app.modules.notifications.services.notification_service import (
    NotificationService,
)
from app.modules.scheduling.models.presentation_model import PresentationPurposeEnum
from app.modules.scheduling.repositories.scheduling_repository import (
    SchedulingRepository,
)
from app.modules.scheduling.schemas.scheduling_schema import (
    AppointmentCancelRequest,
    AppointmentOutcomeRequest,
    AppointmentRescheduleRequest,
    AvailabilityCreateRequest,
    AvailabilityUpdateRequest,
    PresentationSlotResponse,
    SlotReserveRequest,
    SchedulingRequestCreateRequest,
    SchedulingRequestRespondRequest,
    SchedulingRequestRejectRequest,
    SchedulingRequestResponse,
    SchedulingConfigResponse,
    SchedulingConfigUpdateRequest,
    DirectSchedulingRequest,
    AppointmentDocumentUpdateRequest,
)
from app.modules.scheduling.services.scheduling_service import SchedulingService


router = APIRouter(prefix="/scheduling", tags=["Scheduling"])


def _build_service(db: AsyncSession) -> SchedulingService:
    notification_service = NotificationService(
        notification_repository=NotificationRepository(db),
        app_config=config,
    )

    return SchedulingService(
        repository=SchedulingRepository(db),
        notification_service=notification_service,
    )


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


@router.patch(
    "/appointments/{appointment_id}/outcome",
    response_model=PresentationSlotResponse,
)
async def register_appointment_outcome(
    appointment_id: int,
    payload: AppointmentOutcomeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PresentationSlotResponse:
    """Registra asistencia, resultado y observaciones de una cita."""

    service = _build_service(db)
    slot = await service.register_appointment_outcome(
        appointment_id=appointment_id,
        actor=current_user,
        payload=payload,
    )

    return PresentationSlotResponse.model_validate(slot)


@router.post(
    "/appointments/direct",
    response_model=PresentationSlotResponse,
    status_code=status.HTTP_201_CREATED,
)
async def schedule_direct_appointment(
    payload: DirectSchedulingRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PresentationSlotResponse:
    """Agenda una presentación final directamente para la práctica de un estudiante, sin solicitud previa."""

    service = _build_service(db)
    appointment = await service.schedule_direct_appointment(
        actor=current_user,
        payload=payload,
    )

    return PresentationSlotResponse.model_validate(appointment)



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


@router.post(
    "/requests",
    response_model=SchedulingRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_scheduling_request(
    payload: SchedulingRequestCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SchedulingRequestResponse:
    """Crea una solicitud de agendamiento para consulta general o presentación final."""

    service = _build_service(db)
    request = await service.create_scheduling_request(actor=current_user, payload=payload)
    return SchedulingRequestResponse.model_validate(request)


@router.get("/requests/me", response_model=list[SchedulingRequestResponse])
async def list_my_requests(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[SchedulingRequestResponse]:
    """Lista las solicitudes de agendamiento creadas por el estudiante autenticado."""

    service = _build_service(db)
    requests = await service.list_my_requests(actor=current_user)
    return [SchedulingRequestResponse.model_validate(req) for req in requests]


@router.get("/requests", response_model=list[SchedulingRequestResponse])
async def list_pending_requests(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[SchedulingRequestResponse]:
    """Lista todas las solicitudes pendientes de agendamiento para coordinadores."""

    service = _build_service(db)
    requests = await service.list_pending_requests(actor=current_user)
    return [SchedulingRequestResponse.model_validate(req) for req in requests]


@router.post("/requests/{id}/respond", response_model=SchedulingRequestResponse)
async def respond_to_request(
    id: int,
    payload: SchedulingRequestRespondRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SchedulingRequestResponse:
    """Responde a una solicitud asignando una fecha/hora y creando la cita agendada."""

    service = _build_service(db)
    request = await service.respond_to_request(actor=current_user, request_id=id, payload=payload)
    return SchedulingRequestResponse.model_validate(request)


@router.post("/requests/{id}/reject", response_model=SchedulingRequestResponse)
async def reject_request(
    id: int,
    payload: SchedulingRequestRejectRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SchedulingRequestResponse:
    """Rechaza una solicitud de agendamiento indicando un motivo."""

    service = _build_service(db)
    request = await service.reject_request(actor=current_user, request_id=id, payload=payload)
    return SchedulingRequestResponse.model_validate(request)


@router.post("/requests/{id}/cancel", response_model=SchedulingRequestResponse)
async def cancel_request(
    id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SchedulingRequestResponse:
    """Cancela una solicitud de agendamiento pendiente propia."""

    service = _build_service(db)
    request = await service.cancel_request(actor=current_user, request_id=id)
    return SchedulingRequestResponse.model_validate(request)


@router.get("/config")
async def get_scheduling_config(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Obtiene la configuración de consultas generales habilitadas."""

    service = _build_service(db)
    return await service.get_scheduling_config(actor=current_user)


@router.patch("/config", response_model=SchedulingConfigResponse)
async def toggle_general_consultations(
    payload: SchedulingConfigUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SchedulingConfigResponse:
    """Habilita o deshabilita las consultas generales para el coordinador autenticado."""

    service = _build_service(db)
    config = await service.toggle_general_consultations(actor=current_user, payload=payload)
    return SchedulingConfigResponse.model_validate(config)


@router.patch(
    "/appointments/{appointment_id}/confirm",
    response_model=PresentationSlotResponse,
)
async def confirm_appointment(
    appointment_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PresentationSlotResponse:
    """Confirma la asistencia a una cita agendada por parte del estudiante."""

    service = _build_service(db)
    slot = await service.confirm_appointment(appointment_id=appointment_id, actor=current_user)

    return PresentationSlotResponse.model_validate(slot)


@router.patch(
    "/appointments/{appointment_id}/document",
    response_model=PresentationSlotResponse,
)
async def update_appointment_document(
    appointment_id: int,
    payload: AppointmentDocumentUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PresentationSlotResponse:
    """Asocia un documento de diapositivas a una cita existente."""

    service = _build_service(db)
    slot = await service.update_appointment_document(
        appointment_id=appointment_id,
        document_id=payload.document_id,
        actor=current_user,
    )

    return PresentationSlotResponse.model_validate(slot)

