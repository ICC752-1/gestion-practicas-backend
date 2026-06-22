"""Servicio de negocio para publicacion y reserva de agenda."""

import logging
from datetime import UTC, date, datetime, time, timedelta

from fastapi import HTTPException, status

from app.modules.auth.models.user_model import User
from app.modules.internships.models.internship_model import (
    CompletionStatusEnum,
    FinalResultEnum,
)
from app.modules.notifications.services.notification_service import (
    NotificationService,
)
from app.modules.notifications.utils.notification_event_helpers import (
    build_appointment_scheduled_notification,
)
from app.modules.scheduling.models.presentation_model import (
    Presentation,
    PresentationPurposeEnum,
    PresentationResultEnum,
    PresentationStatusEnum,
)
import json
from app.modules.scheduling.repositories.scheduling_repository import (
    SchedulingRepository,
)
from app.modules.scheduling.models.scheduling_config_model import SchedulingConfig
from app.modules.scheduling.models.scheduling_request_model import (
    SchedulingRequest,
    SchedulingRequestStatusEnum,
)
from app.modules.scheduling.schemas.scheduling_schema import (
    AppointmentCancelRequest,
    AppointmentOutcomeRequest,
    AppointmentRescheduleRequest,
    AvailabilityCreateRequest,
    AvailabilityUpdateRequest,
    SlotReserveRequest,
    SchedulingRequestCreateRequest,
    SchedulingRequestRespondRequest,
    SchedulingRequestRejectRequest,
    SchedulingConfigUpdateRequest,
    DirectSchedulingRequest,
)


logger = logging.getLogger(__name__)

ADMIN_ROLES = {
    "Encargado de practica",
    "Director de carrera",
}
STUDENT_ROLE = "Estudiante"
DIRECTOR_ROLE = "Director de carrera"

ROLE_DISPLAY_MAPPING = {
    "Director de carrera": "Director",
    "Encargado de practica": "Coordinador",
}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _role_names(user: User) -> set[str]:
    return {user_role.role.name for user_role in user.roles}


def _display_role_for(user: User) -> str | None:
    """Traduce el rol administrativo del actor a su etiqueta de display."""

    roles = _role_names(user)
    for role_name, display in ROLE_DISPLAY_MAPPING.items():
        if role_name in roles:
            return display
    return None


def _combine(slot_date: date, slot_time: time) -> datetime:
    return datetime.combine(slot_date, slot_time)


def _today() -> date:
    return _now().date()


class SchedulingService:
    """Aplica reglas de disponibilidad, reservas y cancelaciones."""

    def __init__(
        self,
        repository: SchedulingRepository,
        notification_service: NotificationService | None = None,
    ) -> None:
        self.repository = repository
        self.notification_service = notification_service

    async def _dispatch_notification(self, notification) -> None:
        """Despacha una notificacion a traves del servicio de notificaciones.

        Si el servicio no esta configurado, la operacion se ignora. Los errores
        de notificacion no interrumpen el flujo principal de negocio.
        """

        if self.notification_service is None:
            return

        try:
            await self.notification_service.create_and_dispatch(notification)
        except Exception:
            logger.warning(
                "Fallo al despachar notificacion (event=%s). "
                "El flujo de negocio continua normalmente.",
                notification.event_type,
                exc_info=True,
            )

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

    def _require_owner_admin_for_appointment(
        self,
        slot: Presentation,
        actor: User,
    ) -> None:
        if not self._is_admin(actor) or slot.owner_id != actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No puedes registrar resultados de una cita ajena",
            )

    async def _sync_final_presentation_pending_state(
        self,
        internship,
    ) -> None:
        if internship is None or internship.is_cancelled:
            return

        if internship.completion_status == CompletionStatusEnum.finalized:
            return

        if internship.end_date > _today():
            return

        has_supervisor_evaluation = await self.repository.has_supervisor_evaluation(
            internship.id
        )
        internship.completion_status = (
            CompletionStatusEnum.pending_presentation
            if has_supervisor_evaluation
            else CompletionStatusEnum.pending_evaluations
        )

    async def _validate_final_presentation_requirements(
        self,
        internship,
    ) -> None:
        pending_requirements: list[str] = []

        if internship.end_date > _today():
            pending_requirements.append("La práctica aún no alcanza su fecha de término")

        has_supervisor_evaluation = await self.repository.has_supervisor_evaluation(
            internship.id
        )
        if not has_supervisor_evaluation:
            pending_requirements.append(
                "Falta la evaluación del supervisor para cerrar la práctica"
            )

        if pending_requirements:
            await self._sync_final_presentation_pending_state(internship)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": (
                        "La presentación final no puede cerrarse porque aún hay "
                        "requisitos pendientes."
                    ),
                    "pending_requirements": pending_requirements,
                },
            )

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

        if (
            slot.purpose == PresentationPurposeEnum.initial_interview
            and internship.completion_status == CompletionStatusEnum.not_started
        ):
            internship.completion_status = CompletionStatusEnum.in_progress

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

    async def register_appointment_outcome(
        self,
        appointment_id: int,
        actor: User,
        payload: AppointmentOutcomeRequest,
    ) -> Presentation:
        """Registra asistencia, resultado y observaciones de una cita."""

        slot = await self.repository.get_slot_by_id_for_update(appointment_id)
        if slot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cita no encontrada",
            )

        if slot.status != PresentationStatusEnum.scheduled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Solo se pueden registrar resultados sobre citas agendadas",
            )

        self._require_owner_admin_for_appointment(slot=slot, actor=actor)

        if (
            payload.attendance_status == PresentationStatusEnum.completed.value
            and payload.result is None
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debes indicar un resultado cuando la cita fue realizada",
            )

        internship = None
        if slot.internship_id is not None:
            internship = await self.repository.get_internship_by_id(slot.internship_id)

        if (
            slot.purpose == PresentationPurposeEnum.final_presentation
            and payload.attendance_status == PresentationStatusEnum.completed.value
        ):
            if internship is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="La presentación final debe estar asociada a una práctica",
                )
            await self._validate_final_presentation_requirements(internship)

        timestamp = _now()
        slot.status = PresentationStatusEnum(payload.attendance_status)
        slot.result = payload.result if slot.status == PresentationStatusEnum.completed else None
        slot.comments = None if payload.comments is None else payload.comments.strip() or None
        slot.updated_at = timestamp

        if internship is not None:
            if slot.purpose == PresentationPurposeEnum.initial_interview:
                if slot.status == PresentationStatusEnum.completed:
                    internship.completion_status = CompletionStatusEnum.in_progress
            elif slot.purpose == PresentationPurposeEnum.final_presentation:
                if slot.status == PresentationStatusEnum.no_show:
                    await self._sync_final_presentation_pending_state(internship)
                else:
                    internship.completion_status = CompletionStatusEnum.finalized
                    internship.final_result = (
                        FinalResultEnum.passed
                        if payload.result == PresentationResultEnum.approved
                        else FinalResultEnum.failed
                    )
                    internship.blocks_new_registration = (
                        internship.final_result != FinalResultEnum.failed
                    )

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

    async def create_scheduling_request(
        self,
        actor: User,
        payload: SchedulingRequestCreateRequest,
    ) -> SchedulingRequest:
        """Crea una solicitud de agendamiento para consulta general o presentación final."""

        self._require_student(actor)

        # 1. Validaciones por tipo de agendamiento
        if payload.purpose == PresentationPurposeEnum.general_consultation:
            # Verificar si las consultas generales están activadas por algún coordinador
            any_enabled = await self.repository.has_any_general_consultation_enabled()
            if not any_enabled:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Las consultas generales no están habilitadas en este momento",
                )

            # Validar que el coordinador destino esté habilitado para consultas
            if payload.target_coordinator_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Debes seleccionar un coordinador para la consulta general",
                )

            active_coordinators = (
                await self.repository.list_active_coordinators_for_consultations()
            )
            active_ids = {coord.id for coord in active_coordinators}
            if payload.target_coordinator_id not in active_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "El coordinador seleccionado no tiene las consultas "
                        "generales habilitadas"
                    ),
                )
        elif payload.purpose == PresentationPurposeEnum.final_presentation:
            if not payload.internship_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El ID de práctica es requerido para presentaciones finales",
                )

            internship = await self.repository.get_internship_by_id(payload.internship_id)
            if not internship:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Práctica no encontrada",
                )

            if internship.user_id != actor.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes permisos para esta práctica",
                )

            if internship.is_cancelled:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No puedes solicitar agendamiento para una práctica cancelada",
                )

            if internship.completion_status == CompletionStatusEnum.finalized:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="La práctica ya se encuentra finalizada",
                )

            # Requisitos previos: autoevaluación enviada
            has_self_eval = await self.repository.has_self_evaluation(internship.id)
            if not has_self_eval:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Debes completar y enviar tu autoevaluación primero",
                )

            # Requisitos previos: evaluación del supervisor aprobada (recomendación recomendada o con observaciones)
            sup_rec = await self.repository.get_supervisor_evaluation_recommendation(internship.id)
            if not sup_rec:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Falta la evaluación del supervisor",
                )

            if sup_rec not in ("recommended", "recommended_with_observations"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La evaluación del supervisor no es aprobatoria",
                )

        # 2. Evitar solicitudes duplicadas pendientes del mismo tipo
        existing_requests = await self.repository.list_requests_for_student(actor.id)
        for req in existing_requests:
            if req.status == SchedulingRequestStatusEnum.pending and req.purpose == payload.purpose:
                if payload.purpose == PresentationPurposeEnum.general_consultation:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Ya tienes una solicitud de consulta general pendiente",
                    )
                elif req.internship_id == payload.internship_id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Ya tienes una solicitud de presentación final pendiente para esta práctica",
                    )

        # 3. Serializar fechas preferidas
        preferred_dates_str = json.dumps([d.isoformat() for d in payload.preferred_dates])

        # 4. Crear la solicitud
        request = SchedulingRequest(
            student_id=actor.id,
            internship_id=payload.internship_id,
            purpose=payload.purpose,
            message=payload.message,
            preferred_dates=preferred_dates_str,
            status=SchedulingRequestStatusEnum.pending,
            target_coordinator_id=(
                payload.target_coordinator_id
                if payload.purpose == PresentationPurposeEnum.general_consultation
                else None
            ),
        )

        return await self.repository.create_scheduling_request(request)

    async def respond_to_request(
        self,
        actor: User,
        request_id: int,
        payload: SchedulingRequestRespondRequest,
    ) -> SchedulingRequest:
        """Responde a una solicitud creando la cita y marcando la solicitud como agendada."""

        self._require_admin(actor)

        request = await self.repository.get_scheduling_request_by_id(request_id)
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitud de agendamiento no encontrada",
            )

        if request.status != SchedulingRequestStatusEnum.pending:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Solo se pueden responder solicitudes pendientes",
            )

        self._ensure_future_slot(payload.date, payload.start_time)

        # Validar solapamiento del coordinador
        has_overlap = await self.repository.has_owner_overlap(
            owner_id=actor.id,
            slot_date=payload.date,
            start_time=payload.start_time,
            end_time=payload.end_time,
        )
        if has_overlap:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya tienes una cita agendada en ese rango horario",
            )

        # Validar solapamiento del estudiante
        has_student_overlap = await self.repository.has_student_overlap(
            user_id=request.student_id,
            slot_date=payload.date,
            start_time=payload.start_time,
            end_time=payload.end_time,
        )
        if has_student_overlap:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El estudiante ya tiene una cita agendada en ese rango horario",
            )

        # Calcular duración
        duration = int(
            (_combine(payload.date, payload.end_time) - _combine(payload.date, payload.start_time)).total_seconds()
            // 60
        )

        # Crear Presentation (cita)
        presentation = Presentation(
            date=payload.date,
            start_time=payload.start_time,
            end_time=payload.end_time,
            duration_minutes=duration,
            modality=payload.modality,
            purpose=request.purpose,
            status=PresentationStatusEnum.scheduled,
            location=payload.location,
            comments=payload.comments,
            owner_id=actor.id,
            user_id=request.student_id,
            internship_id=request.internship_id,
            reserved_at=_now(),
        )

        # Guardar Presentation
        created_presentations = await self.repository.create_slots([presentation])
        created_presentation = created_presentations[0]

        # Actualizar solicitud
        timestamp = _now()
        request.status = SchedulingRequestStatusEnum.scheduled
        request.coordinator_id = actor.id
        request.coordinator_response = payload.comments
        request.scheduled_date = payload.date
        request.scheduled_start_time = payload.start_time
        request.scheduled_end_time = payload.end_time
        request.scheduled_modality = payload.modality
        request.scheduled_location = payload.location
        request.presentation_id = created_presentation.id
        request.resolved_by_role = _display_role_for(actor)
        request.resolved_at = timestamp
        request.updated_at = timestamp

        # Cambiar estado de práctica si es entrevista inicial
        if (
            request.purpose == PresentationPurposeEnum.initial_interview
            and request.internship_id is not None
        ):
            internship = await self.repository.get_internship_by_id(request.internship_id)
            if internship and internship.completion_status == CompletionStatusEnum.not_started:
                internship.completion_status = CompletionStatusEnum.in_progress

        saved_request = await self.repository.save_scheduling_request(request)

        # Despachar notificación de cita agendada al estudiante
        if self.notification_service is not None and request.student_id is not None:
            student_email = None
            try:
                student = getattr(request, "student", None)
                if student is not None:
                    student_email = getattr(student, "email", None)
            except Exception:
                student_email = None

            scheduled_time_label = (
                f"{payload.start_time.strftime('%H:%M')} - "
                f"{payload.end_time.strftime('%H:%M')}"
            )
            await self._dispatch_notification(
                build_appointment_scheduled_notification(
                    recipient_user_id=request.student_id,
                    recipient_email=student_email,
                    scheduling_request_id=request.id,
                    presentation_id=created_presentation.id,
                    scheduled_date=payload.date.isoformat(),
                    scheduled_time=scheduled_time_label,
                    modality=payload.modality,
                    location=payload.location,
                    resolved_by_role=request.resolved_by_role,
                )
            )

        return saved_request

    async def schedule_direct_appointment(
        self,
        actor: User,
        payload: DirectSchedulingRequest,
    ) -> Presentation:
        """Agenda una presentación final directamente para la práctica de un estudiante, sin solicitud previa."""
        self._require_admin(actor)

        # 1. Validar que la práctica exista, no esté cancelada ni finalizada
        internship = await self.repository.get_internship_by_id(payload.internship_id)
        if internship is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Práctica no encontrada",
            )

        if internship.is_cancelled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No puedes agendar citas para una práctica cancelada",
            )

        if internship.completion_status == CompletionStatusEnum.finalized:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La práctica ya se encuentra finalizada",
            )

        # 2. Validar que no tenga otra presentación final agendada o completada
        has_duplicate = await self.repository.has_active_appointment_for_internship(
            internship_id=internship.id,
            purpose=PresentationPurposeEnum.final_presentation,
        )
        if has_duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La práctica ya tiene una presentación final agendada o completada",
            )

        # 3. Validar rango de fecha futuro
        self._ensure_future_slot(payload.date, payload.start_time)

        # 4. Validar solapamiento del coordinador (owner_id = actor.id)
        has_owner_overlap = await self.repository.has_owner_overlap(
            owner_id=actor.id,
            slot_date=payload.date,
            start_time=payload.start_time,
            end_time=payload.end_time,
        )
        if has_owner_overlap:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya tienes una cita agendada en ese rango horario",
            )

        # 5. Validar solapamiento del estudiante (user_id = internship.user_id)
        has_student_overlap = await self.repository.has_student_overlap(
            user_id=internship.user_id,
            slot_date=payload.date,
            start_time=payload.start_time,
            end_time=payload.end_time,
        )
        if has_student_overlap:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El estudiante ya tiene una cita agendada en ese rango horario",
            )

        # 6. Calcular duración
        duration = int(
            (_combine(payload.date, payload.end_time) - _combine(payload.date, payload.start_time)).total_seconds()
            // 60
        )

        # 7. Crear la cita (Presentation)
        presentation = Presentation(
            date=payload.date,
            start_time=payload.start_time,
            end_time=payload.end_time,
            duration_minutes=duration,
            modality=payload.modality,
            purpose=PresentationPurposeEnum.final_presentation,
            status=PresentationStatusEnum.scheduled,
            location=payload.location,
            comments=payload.comments,
            owner_id=actor.id,
            user_id=internship.user_id,
            internship_id=internship.id,
            reserved_at=_now(),
        )

        created_presentations = await self.repository.create_slots([presentation])
        created_presentation = created_presentations[0]

        # 8. Despachar notificación al estudiante (bandeja + email)
        if self.notification_service is not None:
            student_email = None
            try:
                student = getattr(internship, "student", None)
                if student is not None:
                    student_email = getattr(student, "email", None)
            except Exception:
                student_email = None

            scheduled_time_label = (
                f"{payload.start_time.strftime('%H:%M')} - "
                f"{payload.end_time.strftime('%H:%M')}"
            )
            await self._dispatch_notification(
                build_appointment_scheduled_notification(
                    recipient_user_id=internship.user_id,
                    recipient_email=student_email,
                    scheduling_request_id=None,
                    presentation_id=created_presentation.id,
                    scheduled_date=payload.date.isoformat(),
                    scheduled_time=scheduled_time_label,
                    modality=payload.modality,
                    location=payload.location,
                    resolved_by_role=_display_role_for(actor),
                )
            )

        return created_presentation

    async def reject_request(
        self,
        actor: User,
        request_id: int,
        payload: SchedulingRequestRejectRequest,
    ) -> SchedulingRequest:
        """Rechaza una solicitud de agendamiento con un motivo."""

        self._require_admin(actor)

        request = await self.repository.get_scheduling_request_by_id(request_id)
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitud de agendamiento no encontrada",
            )

        if request.status != SchedulingRequestStatusEnum.pending:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Solo se pueden rechazar solicitudes pendientes",
            )

        timestamp = _now()
        request.status = SchedulingRequestStatusEnum.rejected
        request.coordinator_id = actor.id
        request.coordinator_response = payload.reason
        request.resolved_by_role = _display_role_for(actor)
        request.resolved_at = timestamp
        request.updated_at = timestamp

        return await self.repository.save_scheduling_request(request)

    async def cancel_request(
        self,
        actor: User,
        request_id: int,
    ) -> SchedulingRequest:
        """Cancela una solicitud de agendamiento por parte del estudiante propietario."""

        self._require_student(actor)

        request = await self.repository.get_scheduling_request_by_id(request_id)
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitud de agendamiento no encontrada",
            )

        if request.student_id != actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para cancelar esta solicitud",
            )

        if request.status != SchedulingRequestStatusEnum.pending:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Solo se pueden cancelar solicitudes pendientes",
            )

        timestamp = _now()
        request.status = SchedulingRequestStatusEnum.cancelled
        request.resolved_at = timestamp
        request.updated_at = timestamp

        return await self.repository.save_scheduling_request(request)

    async def list_pending_requests(self, actor: User) -> list[SchedulingRequest]:
        """Obtiene las solicitudes pendientes dirigidas al coordinador autenticado.

        Incluye las solicitudes dirigidas explícitamente al actor y las solicitudes
        legacy sin destinatario (``target_coordinator_id`` nulo).
        """

        self._require_admin(actor)
        return await self.repository.list_pending_requests(actor_id=actor.id)

    async def list_my_requests(self, actor: User) -> list[SchedulingRequest]:
        """Obtiene todas las solicitudes de agendamiento del estudiante autenticado."""

        self._require_student(actor)
        return await self.repository.list_requests_for_student(actor.id)

    async def get_scheduling_config(self, actor: User) -> dict:
        """Obtiene la configuración de agendamiento según el rol.

        - Estudiante: indicador global de consultas habilitadas y la lista de
          coordinadores activos para consultas generales.
        - Admin: configuración propia del coordinador, incluyendo el flag global
          de inscripción de prácticas desactivada.
        """

        if self._is_student(actor):
            enabled = await self.repository.has_any_general_consultation_enabled()
            active_coordinators = (
                await self.repository.list_active_coordinators_for_consultations()
            )
            return {
                "general_consultations_enabled": enabled,
                "active_coordinators": [
                    {
                        "id": coord.id,
                        "first_name": coord.first_name,
                        "last_name": coord.last_name,
                        "email": coord.email,
                        "role_name": _display_role_for(coord),
                    }
                    for coord in active_coordinators
                ],
            }

        if self._is_admin(actor):
            config = await self.repository.get_scheduling_config(actor.id)
            if not config:
                config = await self.repository.upsert_scheduling_config(actor.id)
            return {
                "id": config.id,
                "coordinator_id": config.coordinator_id,
                "general_consultations_enabled": config.general_consultations_enabled,
                "internship_applications_disabled": config.internship_applications_disabled,
                "updated_at": config.updated_at,
            }

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rol no autorizado para ver configuración",
        )

    async def toggle_general_consultations(
        self,
        actor: User,
        payload: SchedulingConfigUpdateRequest,
    ) -> SchedulingConfig:
        """Actualiza la configuración de agendamiento según el rol del actor.

        - ``Encargado de practica``: sólo puede modificar
          ``general_consultations_enabled``.
        - ``Director de carrera``: puede modificar ambos flags
          (``general_consultations_enabled`` e
          ``internship_applications_disabled``).

        Sólo se persisten los campos provistos en el payload.
        """

        self._require_admin(actor)

        is_director = DIRECTOR_ROLE in _role_names(actor)

        if (
            payload.internship_applications_disabled is not None
            and not is_director
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Sólo el Director de carrera puede desactivar la inscripción "
                    "de prácticas"
                ),
            )

        return await self.repository.upsert_scheduling_config(
            actor.id,
            general_consultations_enabled=payload.general_consultations_enabled,
            internship_applications_disabled=(
                payload.internship_applications_disabled
                if is_director
                else None
            ),
        )

