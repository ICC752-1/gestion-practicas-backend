"""Servicio de negocio para publicacion y reserva de agenda."""

from datetime import UTC, date, datetime, time, timedelta

from fastapi import HTTPException, status

from app.modules.auth.models.user_model import User
from app.modules.scheduling.models.presentation_model import (
    Presentation,
    PresentationPurposeEnum,
    PresentationStatusEnum,
)
from app.modules.scheduling.repositories.scheduling_repository import (
    SchedulingRepository,
)
from app.modules.scheduling.schemas.scheduling_schema import (
    AppointmentCancelRequest,
    AppointmentRescheduleRequest,
    AvailabilityCreateRequest,
    AvailabilityUpdateRequest,
    SlotReserveRequest,
)


ADMIN_ROLES = {
    "Encargado de practica",
    "Director de carrera",
}
STUDENT_ROLE = "Estudiante"


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _role_names(user: User) -> set[str]:
    return {user_role.role.name for user_role in user.roles}


def _combine(slot_date: date, slot_time: time) -> datetime:
    return datetime.combine(slot_date, slot_time)


class SchedulingService:
    """Aplica reglas de disponibilidad, reservas y cancelaciones."""

    def __init__(self, repository: SchedulingRepository) -> None:
        self.repository = repository

    def _require_admin(self, user: User) -> None:
        if not (_role_names(user) & ADMIN_ROLES):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para administrar la agenda",
            )

    def _require_student(self, user: User) -> None:
        if STUDENT_ROLE not in _role_names(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo estudiantes pueden reservar horarios",
            )

    def _is_admin(self, user: User) -> bool:
        return bool(_role_names(user) & ADMIN_ROLES)

    def _is_student(self, user: User) -> bool:
        return STUDENT_ROLE in _role_names(user)

    def _ensure_future_slot(self, slot_date: date, slot_time: time) -> None:
        if _combine(slot_date, slot_time) <= _now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El horario debe ser futuro",
            )

    def _ensure_owned_available_slot(self, slot: Presentation, actor: User) -> None:
        if slot.owner_id != actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No puedes administrar disponibilidad de otro usuario",
            )

        if slot.status != PresentationStatusEnum.available:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Solo se puede administrar disponibilidad activa",
            )

        self._ensure_future_slot(slot.date, slot.start_time)

    async def create_availability(
        self,
        actor: User,
        payload: AvailabilityCreateRequest,
    ) -> list[Presentation]:
        """Publica bloques consecutivos de disponibilidad."""

        self._require_admin(actor)
        self._ensure_future_slot(payload.date, payload.start_time)

        start_dt = _combine(payload.date, payload.start_time)
        end_dt = _combine(payload.date, payload.end_time)
        duration = timedelta(minutes=payload.duration_minutes)

        slots: list[Presentation] = []
        cursor = start_dt

        while cursor + duration <= end_dt:
            slot_start = cursor.time()
            slot_end = (cursor + duration).time()

            has_overlap = await self.repository.has_owner_overlap(
                owner_id=actor.id,
                slot_date=payload.date,
                start_time=slot_start,
                end_time=slot_end,
            )

            if has_overlap:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Ya existe disponibilidad o cita en ese rango horario",
                )

            slots.append(
                Presentation(
                    date=payload.date,
                    start_time=slot_start,
                    end_time=slot_end,
                    duration_minutes=payload.duration_minutes,
                    modality=payload.modality,
                    purpose=payload.purpose,
                    status=PresentationStatusEnum.available,
                    location=payload.location,
                    timezone=payload.timezone,
                    comments=payload.comments,
                    owner_id=actor.id,
                )
            )
            cursor += duration

        if not slots:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El rango horario no permite generar bloques",
            )

        return await self.repository.create_slots(slots)

    async def list_available_slots(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        purpose: PresentationPurposeEnum | None = None,
    ) -> list[Presentation]:
        """Lista horarios publicados aun disponibles."""

        return await self.repository.list_available_slots(
            date_from=date_from,
            date_to=date_to,
            purpose=purpose,
        )

    async def list_my_appointments(self, actor: User) -> list[Presentation]:
        """Lista citas agendadas segun el rol del usuario autenticado."""

        if self._is_admin(actor):
            return await self.repository.list_appointments_for_owner(actor.id)

        if self._is_student(actor):
            return await self.repository.list_appointments_for_student(actor.id)

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para consultar citas",
        )

    async def reserve_slot(
        self,
        slot_id: int,
        actor: User,
        payload: SlotReserveRequest,
    ) -> Presentation:
        """Reserva un bloque disponible para una practica del estudiante."""

        self._require_student(actor)

        slot = await self.repository.get_slot_by_id_for_update(slot_id)
        if slot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Horario no encontrado",
            )

        if slot.status != PresentationStatusEnum.available:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El horario ya no se encuentra disponible",
            )

        self._ensure_future_slot(slot.date, slot.start_time)

        internship = await self.repository.get_internship_by_id(payload.internship_id)
        if internship is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Practica no encontrada",
            )

        if internship.user_id != actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No puedes reservar para una practica de otro estudiante",
            )

        if internship.is_cancelled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No puedes reservar una practica anulada",
            )

        has_duplicate = await self.repository.has_active_appointment_for_internship(
            internship_id=internship.id,
            purpose=slot.purpose,
        )
        if has_duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La practica ya tiene una cita agendada para este tipo",
            )

        has_overlap = await self.repository.has_student_overlap(
            user_id=actor.id,
            slot_date=slot.date,
            start_time=slot.start_time,
            end_time=slot.end_time,
            exclude_slot_id=slot.id,
        )
        if has_overlap:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya tienes una cita agendada en ese rango horario",
            )

        timestamp = _now()
        slot.status = PresentationStatusEnum.scheduled
        slot.user_id = actor.id
        slot.internship_id = internship.id
        slot.reserved_at = timestamp
        slot.updated_at = timestamp

        return await self.repository.save_slot(slot)

    async def cancel_appointment(
        self,
        appointment_id: int,
        actor: User,
        payload: AppointmentCancelRequest,
    ) -> Presentation:
        """Cancela una cita agendada por estudiante o administrativo."""

        slot = await self.repository.get_slot_by_id_for_update(appointment_id)
        if slot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cita no encontrada",
            )

        if slot.status != PresentationStatusEnum.scheduled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Solo se pueden cancelar citas agendadas",
            )

        is_owner_admin = self._is_admin(actor) and slot.owner_id == actor.id
        is_student_owner = self._is_student(actor) and slot.user_id == actor.id

        if not (is_owner_admin or is_student_owner):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para cancelar esta cita",
            )

        reason = None if payload.reason is None else payload.reason.strip()
        if is_owner_admin and not reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El motivo de cancelacion es obligatorio",
            )

        timestamp = _now()
        slot.status = PresentationStatusEnum.cancelled
        slot.cancel_reason = reason
        slot.cancelled_at = timestamp
        slot.updated_at = timestamp

        return await self.repository.save_slot(slot)

    async def reschedule_appointment(
        self,
        appointment_id: int,
        actor: User,
        payload: AppointmentRescheduleRequest,
    ) -> Presentation:
        """Mueve una cita del estudiante a otro bloque disponible."""

        self._require_student(actor)

        appointment = await self.repository.get_slot_by_id_for_update(appointment_id)
        if appointment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cita no encontrada",
            )

        if appointment.status != PresentationStatusEnum.scheduled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Solo se pueden reprogramar citas agendadas",
            )

        if appointment.user_id != actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para reprogramar esta cita",
            )

        new_slot = await self.repository.get_slot_by_id_for_update(payload.new_slot_id)
        if new_slot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nuevo horario no encontrado",
            )

        if new_slot.status != PresentationStatusEnum.available:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El nuevo horario ya no se encuentra disponible",
            )

        if new_slot.purpose != appointment.purpose:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El nuevo horario no corresponde al mismo tipo de cita",
            )

        self._ensure_future_slot(new_slot.date, new_slot.start_time)

        has_overlap = await self.repository.has_student_overlap(
            user_id=actor.id,
            slot_date=new_slot.date,
            start_time=new_slot.start_time,
            end_time=new_slot.end_time,
            exclude_slot_id=appointment.id,
        )
        if has_overlap:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya tienes una cita agendada en ese rango horario",
            )

        timestamp = _now()
        appointment.status = PresentationStatusEnum.cancelled
        appointment.cancel_reason = "Reprogramacion de cita"
        appointment.cancelled_at = timestamp
        appointment.updated_at = timestamp

        new_slot.status = PresentationStatusEnum.scheduled
        new_slot.user_id = actor.id
        new_slot.internship_id = appointment.internship_id
        new_slot.reserved_at = timestamp
        new_slot.updated_at = timestamp

        await self.repository.save_slots([appointment, new_slot])

        return new_slot

    async def close_availability(
        self,
        slot_id: int,
        actor: User,
        payload: AppointmentCancelRequest,
    ) -> Presentation:
        """Cierra un bloque disponible sin reserva."""

        self._require_admin(actor)

        slot = await self.repository.get_slot_by_id_for_update(slot_id)
        if slot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Horario no encontrado",
            )

        self._ensure_owned_available_slot(slot=slot, actor=actor)

        timestamp = _now()
        slot.status = PresentationStatusEnum.closed
        slot.cancel_reason = (
            None if payload.reason is None else payload.reason.strip() or None
        )
        slot.updated_at = timestamp

        return await self.repository.save_slot(slot)

    async def update_availability(
        self,
        slot_id: int,
        actor: User,
        payload: AvailabilityUpdateRequest,
    ) -> Presentation:
        """Edita un bloque futuro de disponibilidad no reservado."""

        self._require_admin(actor)

        slot = await self.repository.get_slot_by_id_for_update(slot_id)
        if slot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Horario no encontrado",
            )

        self._ensure_owned_available_slot(slot=slot, actor=actor)
        self._ensure_future_slot(payload.date, payload.start_time)

        has_overlap = await self.repository.has_owner_overlap(
            owner_id=actor.id,
            slot_date=payload.date,
            start_time=payload.start_time,
            end_time=payload.end_time,
            exclude_slot_id=slot.id,
        )
        if has_overlap:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe disponibilidad o cita en ese rango horario",
            )

        timestamp = _now()
        slot.date = payload.date
        slot.start_time = payload.start_time
        slot.end_time = payload.end_time
        slot.duration_minutes = int(
            (_combine(payload.date, payload.end_time) - _combine(payload.date, payload.start_time)).total_seconds()
            // 60
        )
        slot.modality = payload.modality
        slot.purpose = payload.purpose
        slot.location = payload.location
        slot.timezone = payload.timezone
        slot.comments = payload.comments
        slot.updated_at = timestamp

        return await self.repository.save_slot(slot)

    async def delete_availability(
        self,
        slot_id: int,
        actor: User,
    ) -> None:
        """Elimina un bloque futuro de disponibilidad no reservado."""

        self._require_admin(actor)

        slot = await self.repository.get_slot_by_id_for_update(slot_id)
        if slot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Horario no encontrado",
            )

        self._ensure_owned_available_slot(slot=slot, actor=actor)

        await self.repository.delete_slot(slot)
