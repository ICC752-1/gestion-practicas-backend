from datetime import date, time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.scheduling.models.presentation_model import (
    PresentationPurposeEnum,
    PresentationResultEnum,
    PresentationStatusEnum,
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
)
from app.modules.scheduling.models.scheduling_request_model import (
    SchedulingRequest,
    SchedulingRequestStatusEnum,
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
        end_date=date(2099, 1, 10),
        completion_status="not_started",
        final_result="pending",
        blocks_new_registration=True,
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
        self.deleted_slot = None
        self.has_supervisor_evaluation_result = False
        self.scheduling_requests = {}
        self.scheduling_config = {}
        self.any_general_consultation_enabled = False
        self.supervisor_recommendation = None
        self.has_self_eval = False
        self.created_requests = []
        self.saved_requests = []

    async def create_slots(self, slots):
        self.created_slots = slots
        for i, s in enumerate(slots):
            if not getattr(s, "id", None):
                s.id = 100 + i
        return slots

    async def save_slot(self, slot):
        self.saved_slot = slot
        return slot

    async def save_slots(self, slots):
        self.saved_slots = slots
        return slots

    async def delete_slot(self, slot):
        self.deleted_slot = slot

    async def get_slot_by_id_for_update(self, slot_id: int):
        if self.slot.id == slot_id:
            return self.slot

        if self.new_slot.id == slot_id:
            return self.new_slot

        return None

    async def get_internship_by_id(self, internship_id: int):
        return self.internship if self.internship and self.internship.id == internship_id else None

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

    async def has_supervisor_evaluation(self, internship_id: int) -> bool:
        return self.has_supervisor_evaluation_result

    async def create_scheduling_request(self, request):
        request.id = len(self.scheduling_requests) + 1
        self.scheduling_requests[request.id] = request
        self.created_requests.append(request)
        return request

    async def get_scheduling_request_by_id(self, request_id: int):
        return self.scheduling_requests.get(request_id)

    async def list_requests_for_student(self, student_id: int):
        return [r for r in self.scheduling_requests.values() if r.student_id == student_id]

    async def list_pending_requests(self):
        return [r for r in self.scheduling_requests.values() if r.status == "pending"]

    async def save_scheduling_request(self, request):
        self.scheduling_requests[request.id] = request
        self.saved_requests.append(request)
        return request

    async def get_scheduling_config(self, coordinator_id: int):
        return self.scheduling_config.get(coordinator_id)

    async def has_any_general_consultation_enabled(self) -> bool:
        return self.any_general_consultation_enabled or any(c.general_consultations_enabled for c in self.scheduling_config.values())

    async def upsert_scheduling_config(self, coordinator_id: int, enabled: bool):
        from app.modules.scheduling.models.scheduling_config_model import SchedulingConfig
        config = self.scheduling_config.get(coordinator_id)
        if not config:
            config = SchedulingConfig(
                id=len(self.scheduling_config) + 1,
                coordinator_id=coordinator_id,
                general_consultations_enabled=enabled,
            )
            self.scheduling_config[coordinator_id] = config
        else:
            config.general_consultations_enabled = enabled
        return config

    async def get_supervisor_evaluation_recommendation(self, internship_id: int) -> str | None:
        return self.supervisor_recommendation

    async def has_self_evaluation(self, internship_id: int) -> bool:
        return self.has_self_eval


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


async def test_admin_can_update_own_future_availability() -> None:
    repository = FakeSchedulingRepository()
    service = SchedulingService(repository=repository)

    slot = await service.update_availability(
        slot_id=20,
        actor=_user(2, ["Encargado de practica"]),
        payload=AvailabilityUpdateRequest(
            date=date(2099, 1, 11),
            start_time=time(14, 0),
            end_time=time(14, 45),
            modality="Remoto",
            purpose=PresentationPurposeEnum.final_presentation,
            location="https://meet.test",
            comments="Bloque ajustado",
        ),
    )

    assert slot.date == date(2099, 1, 11)
    assert slot.start_time == time(14, 0)
    assert slot.end_time == time(14, 45)
    assert slot.duration_minutes == 45
    assert slot.modality == "Remoto"
    assert slot.purpose == PresentationPurposeEnum.final_presentation
    assert repository.saved_slot is slot


async def test_update_availability_rejects_owner_overlap() -> None:
    repository = FakeSchedulingRepository()
    repository.owner_overlap = True
    service = SchedulingService(repository=repository)

    with pytest.raises(HTTPException) as exc_info:
        await service.update_availability(
            slot_id=20,
            actor=_user(2, ["Encargado de practica"]),
            payload=AvailabilityUpdateRequest(
                date=date(2099, 1, 10),
                start_time=time(10, 0),
                end_time=time(10, 30),
                modality="Presencial",
                purpose=PresentationPurposeEnum.initial_interview,
            ),
        )

    assert exc_info.value.status_code == 409


async def test_admin_can_delete_own_future_availability() -> None:
    repository = FakeSchedulingRepository()
    service = SchedulingService(repository=repository)

    await service.delete_availability(
        slot_id=20,
        actor=_user(2, ["Encargado de practica"]),
    )

    assert repository.deleted_slot is repository.slot


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
    assert exc_info.value.detail == (
        "El nuevo horario no corresponde al mismo tipo de cita"
    )


async def test_register_initial_interview_outcome_marks_in_progress() -> None:
    repository = FakeSchedulingRepository()
    repository.slot = _slot(status=PresentationStatusEnum.scheduled)
    repository.slot.internship_id = 7
    service = SchedulingService(repository=repository)

    slot = await service.register_appointment_outcome(
        appointment_id=20,
        actor=_user(2, ["Encargado de practica"]),
        payload=AppointmentOutcomeRequest(
            attendance_status="completed",
            result=PresentationResultEnum.approved,
            comments="Entrevista realizada",
        ),
    )

    assert slot.status == PresentationStatusEnum.completed
    assert slot.result == PresentationResultEnum.approved
    assert repository.internship.completion_status == "in_progress"


async def test_register_final_presentation_outcome_requires_prerequisites() -> None:
    repository = FakeSchedulingRepository()
    repository.slot = _slot(status=PresentationStatusEnum.scheduled)
    repository.slot.purpose = PresentationPurposeEnum.final_presentation
    repository.slot.internship_id = 7
    repository.internship.end_date = date(2099, 1, 11)
    service = SchedulingService(repository=repository)

    with pytest.raises(HTTPException) as exc_info:
        await service.register_appointment_outcome(
            appointment_id=20,
            actor=_user(2, ["Encargado de practica"]),
            payload=AppointmentOutcomeRequest(
                attendance_status="completed",
                result=PresentationResultEnum.approved,
            ),
        )

    assert exc_info.value.status_code == 409
    assert "pending_requirements" in exc_info.value.detail


async def test_register_final_presentation_outcome_finalizes_failed_internship() -> None:
    repository = FakeSchedulingRepository()
    repository.slot = _slot(status=PresentationStatusEnum.scheduled)
    repository.slot.purpose = PresentationPurposeEnum.final_presentation
    repository.slot.internship_id = 7
    repository.internship.end_date = date(2026, 1, 9)
    repository.has_supervisor_evaluation_result = True
    service = SchedulingService(repository=repository)

    slot = await service.register_appointment_outcome(
        appointment_id=20,
        actor=_user(2, ["Encargado de practica"]),
        payload=AppointmentOutcomeRequest(
            attendance_status="completed",
            result=PresentationResultEnum.failed,
            comments="Debe repetir la práctica",
        ),
    )

    assert slot.status == PresentationStatusEnum.completed
    assert repository.internship.completion_status == "finalized"
    assert repository.internship.final_result == "failed"
    assert repository.internship.blocks_new_registration is False


# --- NUEVAS PRUEBAS PARA EL MODELO SOLICITUD-RESPUESTA ---

async def test_create_scheduling_request_general_consultation_disabled() -> None:
    repository = FakeSchedulingRepository()
    repository.any_general_consultation_enabled = False
    service = SchedulingService(repository=repository)

    payload = SchedulingRequestCreateRequest(
        purpose=PresentationPurposeEnum.general_consultation,
        preferred_dates=[date(2099, 1, 15)],
        message="Duda sobre el informe",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.create_scheduling_request(
            actor=_user(1, ["Estudiante"]),
            payload=payload,
        )

    assert exc_info.value.status_code == 400
    assert "no están habilitadas" in exc_info.value.detail


async def test_create_scheduling_request_general_consultation_enabled() -> None:
    repository = FakeSchedulingRepository()
    repository.any_general_consultation_enabled = True
    service = SchedulingService(repository=repository)

    payload = SchedulingRequestCreateRequest(
        purpose=PresentationPurposeEnum.general_consultation,
        preferred_dates=[date(2099, 1, 15)],
        message="Duda sobre el informe",
    )

    req = await service.create_scheduling_request(
        actor=_user(1, ["Estudiante"]),
        payload=payload,
    )

    assert req.student_id == 1
    assert req.purpose == PresentationPurposeEnum.general_consultation
    assert req.status == SchedulingRequestStatusEnum.pending
    assert "2099-01-15" in req.preferred_dates


async def test_create_scheduling_request_final_presentation_requires_internship() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        SchedulingRequestCreateRequest(
            purpose=PresentationPurposeEnum.final_presentation,
            preferred_dates=[date(2099, 1, 15)],
        )

    assert "internship_id es requerido para presentaciones finales" in str(exc_info.value)


async def test_create_scheduling_request_final_presentation_missing_evaluations() -> None:
    repository = FakeSchedulingRepository()
    repository.internship = _internship(internship_id=7, user_id=1)
    repository.has_self_eval = False
    repository.supervisor_recommendation = None
    service = SchedulingService(repository=repository)

    payload = SchedulingRequestCreateRequest(
        purpose=PresentationPurposeEnum.final_presentation,
        preferred_dates=[date(2099, 1, 15)],
        internship_id=7,
    )

    # 1. Falta autoevaluación
    with pytest.raises(HTTPException) as exc_info:
        await service.create_scheduling_request(
            actor=_user(1, ["Estudiante"]),
            payload=payload,
        )
    assert exc_info.value.status_code == 400
    assert "autoevaluación" in exc_info.value.detail

    # 2. Tiene autoevaluación, falta supervisor
    repository.has_self_eval = True
    with pytest.raises(HTTPException) as exc_info:
        await service.create_scheduling_request(
            actor=_user(1, ["Estudiante"]),
            payload=payload,
        )
    assert exc_info.value.status_code == 400
    assert "supervisor" in exc_info.value.detail

    # 3. Tiene supervisor pero no aprobada (e.g. not_recommended)
    repository.supervisor_recommendation = "not_recommended"
    with pytest.raises(HTTPException) as exc_info:
        await service.create_scheduling_request(
            actor=_user(1, ["Estudiante"]),
            payload=payload,
        )
    assert exc_info.value.status_code == 400
    assert "no es aprobatoria" in exc_info.value.detail


async def test_create_scheduling_request_final_presentation_success() -> None:
    repository = FakeSchedulingRepository()
    repository.internship = _internship(internship_id=7, user_id=1)
    repository.has_self_eval = True
    repository.supervisor_recommendation = "recommended"
    service = SchedulingService(repository=repository)

    payload = SchedulingRequestCreateRequest(
        purpose=PresentationPurposeEnum.final_presentation,
        preferred_dates=[date(2099, 1, 15)],
        internship_id=7,
    )

    req = await service.create_scheduling_request(
        actor=_user(1, ["Estudiante"]),
        payload=payload,
    )

    assert req.student_id == 1
    assert req.internship_id == 7
    assert req.purpose == PresentationPurposeEnum.final_presentation
    assert req.status == SchedulingRequestStatusEnum.pending


async def test_create_scheduling_request_duplicate_prevention() -> None:
    repository = FakeSchedulingRepository()
    repository.any_general_consultation_enabled = True
    service = SchedulingService(repository=repository)

    payload = SchedulingRequestCreateRequest(
        purpose=PresentationPurposeEnum.general_consultation,
        preferred_dates=[date(2099, 1, 15)],
    )

    # Crear la primera
    await service.create_scheduling_request(
        actor=_user(1, ["Estudiante"]),
        payload=payload,
    )

    # Intentar duplicar
    with pytest.raises(HTTPException) as exc_info:
        await service.create_scheduling_request(
            actor=_user(1, ["Estudiante"]),
            payload=payload,
        )

    assert exc_info.value.status_code == 409
    assert "Ya tienes una solicitud de consulta general pendiente" in exc_info.value.detail


async def test_respond_to_request_requires_admin() -> None:
    repository = FakeSchedulingRepository()
    service = SchedulingService(repository=repository)

    payload = SchedulingRequestRespondRequest(
        date=date(2099, 1, 20),
        start_time=time(10, 0),
        end_time=time(10, 30),
        modality="Presencial",
        location="Oficina 101",
        comments="Hora asignada",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.respond_to_request(
            actor=_user(1, ["Estudiante"]),
            request_id=1,
            payload=payload,
        )

    assert exc_info.value.status_code == 403


async def test_respond_to_request_success() -> None:
    repository = FakeSchedulingRepository()
    repository.any_general_consultation_enabled = True
    service = SchedulingService(repository=repository)

    # 1. Crear la solicitud de consulta general como estudiante
    student = _user(1, ["Estudiante"])
    req = await service.create_scheduling_request(
        actor=student,
        payload=SchedulingRequestCreateRequest(
            purpose=PresentationPurposeEnum.general_consultation,
            preferred_dates=[date(2099, 1, 15)],
        )
    )

    # 2. Responder como coordinador
    admin = _user(2, ["Encargado de practica"])
    payload = SchedulingRequestRespondRequest(
        date=date(2099, 1, 20),
        start_time=time(10, 0),
        end_time=time(10, 30),
        modality="Presencial",
        location="Oficina 101",
        comments="Hora asignada",
    )

    updated_req = await service.respond_to_request(
        actor=admin,
        request_id=req.id,
        payload=payload,
    )

    assert updated_req.status == SchedulingRequestStatusEnum.scheduled
    assert updated_req.coordinator_id == 2
    assert updated_req.scheduled_date == date(2099, 1, 20)
    assert updated_req.scheduled_start_time == time(10, 0)
    assert updated_req.scheduled_modality == "Presencial"
    assert updated_req.scheduled_location == "Oficina 101"
    assert updated_req.presentation_id is not None

    # Verificar que se creó la cita (Presentation)
    assert len(repository.created_slots) == 1
    slot = repository.created_slots[0]
    assert slot.date == date(2099, 1, 20)
    assert slot.start_time == time(10, 0)
    assert slot.end_time == time(10, 30)
    assert slot.owner_id == 2
    assert slot.user_id == 1
    assert slot.status == PresentationStatusEnum.scheduled


async def test_respond_to_request_overlap_validations() -> None:
    repository = FakeSchedulingRepository()
    repository.any_general_consultation_enabled = True
    service = SchedulingService(repository=repository)

    student = _user(1, ["Estudiante"])
    req = await service.create_scheduling_request(
        actor=student,
        payload=SchedulingRequestCreateRequest(
            purpose=PresentationPurposeEnum.general_consultation,
            preferred_dates=[date(2099, 1, 15)],
        )
    )

    admin = _user(2, ["Encargado de practica"])
    payload = SchedulingRequestRespondRequest(
        date=date(2099, 1, 20),
        start_time=time(10, 0),
        end_time=time(10, 30),
        modality="Presencial",
    )

    # 1. Solapamiento de coordinador
    repository.owner_overlap = True
    with pytest.raises(HTTPException) as exc_info:
        await service.respond_to_request(actor=admin, request_id=req.id, payload=payload)
    assert exc_info.value.status_code == 409
    assert "coordinador" in exc_info.value.detail or "rango horario" in exc_info.value.detail
    repository.owner_overlap = False

    # 2. Solapamiento de estudiante
    repository.student_overlap = True
    with pytest.raises(HTTPException) as exc_info:
        await service.respond_to_request(actor=admin, request_id=req.id, payload=payload)
    assert exc_info.value.status_code == 409
    assert "estudiante ya tiene" in exc_info.value.detail


async def test_reject_request() -> None:
    repository = FakeSchedulingRepository()
    repository.any_general_consultation_enabled = True
    service = SchedulingService(repository=repository)

    student = _user(1, ["Estudiante"])
    req = await service.create_scheduling_request(
        actor=student,
        payload=SchedulingRequestCreateRequest(
            purpose=PresentationPurposeEnum.general_consultation,
            preferred_dates=[date(2099, 1, 15)],
        )
    )

    admin = _user(2, ["Encargado de practica"])
    rejected = await service.reject_request(
        actor=admin,
        request_id=req.id,
        payload=SchedulingRequestRejectRequest(reason="No hay cupos"),
    )

    assert rejected.status == SchedulingRequestStatusEnum.rejected
    assert rejected.coordinator_id == 2
    assert rejected.coordinator_response == "No hay cupos"


async def test_cancel_request() -> None:
    repository = FakeSchedulingRepository()
    repository.any_general_consultation_enabled = True
    service = SchedulingService(repository=repository)

    student1 = _user(1, ["Estudiante"])
    student2 = _user(3, ["Estudiante"])

    req = await service.create_scheduling_request(
        actor=student1,
        payload=SchedulingRequestCreateRequest(
            purpose=PresentationPurposeEnum.general_consultation,
            preferred_dates=[date(2099, 1, 15)],
        )
    )

    # 1. Intentar cancelar por otro estudiante
    with pytest.raises(HTTPException) as exc_info:
        await service.cancel_request(actor=student2, request_id=req.id)
    assert exc_info.value.status_code == 403

    # 2. Cancelar con éxito
    cancelled = await service.cancel_request(actor=student1, request_id=req.id)
    assert cancelled.status == SchedulingRequestStatusEnum.cancelled


async def test_get_and_toggle_general_consultations_config() -> None:
    repository = FakeSchedulingRepository()
    service = SchedulingService(repository=repository)

    admin = _user(2, ["Encargado de practica"])
    student = _user(1, ["Estudiante"])

    # 1. Coordinador consulta config (debe inicializarse en False por defecto)
    config = await service.get_scheduling_config(actor=admin)
    assert config["general_consultations_enabled"] is False

    # 2. Estudiante consulta config global (debe ser False porque ningún coordinador activó)
    student_config = await service.get_scheduling_config(actor=student)
    assert student_config["general_consultations_enabled"] is False

    # 3. Coordinador activa consultas
    await service.toggle_general_consultations(
        actor=admin,
        payload=SchedulingConfigUpdateRequest(general_consultations_enabled=True),
    )

    # 4. Coordinador vuelve a consultar
    config = await service.get_scheduling_config(actor=admin)
    assert config["general_consultations_enabled"] is True

    # 5. Estudiante vuelve a consultar config global (ahora debe ser True)
    student_config = await service.get_scheduling_config(actor=student)
    assert student_config["general_consultations_enabled"] is True
