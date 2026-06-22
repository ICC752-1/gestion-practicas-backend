"""Schemas HTTP para disponibilidad y reservas de agenda."""

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

from app.modules.scheduling.models.presentation_model import (
    PresentationPurposeEnum,
    PresentationResultEnum,
    PresentationStatusEnum,
)


Modality = Literal["Presencial", "Remoto", "Híbrido"]


class AvailabilityCreateRequest(BaseModel):
    """Payload para publicar bloques de disponibilidad."""

    model_config = ConfigDict(extra="forbid")

    date: date
    start_time: time
    end_time: time
    duration_minutes: int = Field(default=30, ge=15, le=240)
    modality: Modality
    purpose: PresentationPurposeEnum = PresentationPurposeEnum.initial_interview
    location: str | None = Field(default=None, max_length=500)
    timezone: str = Field(default="America/Santiago", min_length=1, max_length=64)
    comments: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_time_range(self) -> "AvailabilityCreateRequest":
        """Valida que el rango horario permita generar al menos un bloque."""

        if self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time")

        return self


class AvailabilityUpdateRequest(BaseModel):
    """Payload para editar un bloque futuro de disponibilidad."""

    model_config = ConfigDict(extra="forbid")

    date: date
    start_time: time
    end_time: time
    modality: Modality
    purpose: PresentationPurposeEnum
    location: str | None = Field(default=None, max_length=500)
    timezone: str = Field(default="America/Santiago", min_length=1, max_length=64)
    comments: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_time_range(self) -> "AvailabilityUpdateRequest":
        """Valida que el rango horario sea consistente."""

        if self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time")

        return self


class SlotReserveRequest(BaseModel):
    """Payload para reservar un bloque disponible."""

    model_config = ConfigDict(extra="forbid")

    internship_id: int = Field(gt=0)


class AppointmentCancelRequest(BaseModel):
    """Payload para cancelar una cita agendada."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=1000)


class AppointmentRescheduleRequest(BaseModel):
    """Payload para reprogramar una cita a otro bloque disponible."""

    model_config = ConfigDict(extra="forbid")

    new_slot_id: int = Field(gt=0)


class AppointmentOutcomeRequest(BaseModel):
    """Payload para registrar asistencia, resultado y observaciones."""

    model_config = ConfigDict(extra="forbid")

    attendance_status: Literal["completed", "no_show"]
    result: PresentationResultEnum | None = None
    comments: str | None = Field(default=None, max_length=1000)


class PresentationSlotResponse(BaseModel):
    """Respuesta normalizada de un bloque o cita de agenda."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    start_time: time
    end_time: time
    duration_minutes: int
    modality: Modality
    purpose: PresentationPurposeEnum
    status: PresentationStatusEnum
    result: str | None
    location: str | None
    timezone: str
    comments: str | None
    cancel_reason: str | None
    created_at: datetime
    updated_at: datetime
    reserved_at: datetime | None
    cancelled_at: datetime | None
    internship_id: int | None
    user_id: int | None
    owner_id: int


class UserCompactResponse(BaseModel):
    """Información compacta de un usuario (estudiante o coordinador)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str


class SchedulingRequestCreateRequest(BaseModel):
    """Payload para crear una solicitud de agendamiento."""

    model_config = ConfigDict(extra="forbid")

    purpose: PresentationPurposeEnum
    internship_id: int | None = Field(default=None, gt=0)
    message: str | None = Field(default=None, max_length=1000)
    preferred_dates: list[date] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def validate_internship_id(self) -> "SchedulingRequestCreateRequest":
        """Valida que internship_id esté presente si es para presentación final."""
        if self.purpose == PresentationPurposeEnum.final_presentation and not self.internship_id:
            raise ValueError("internship_id es requerido para presentaciones finales")
        return self


class SchedulingRequestRespondRequest(BaseModel):
    """Payload para responder asignando fecha y hora a una solicitud."""

    model_config = ConfigDict(extra="forbid")

    date: date
    start_time: time
    end_time: time
    modality: Modality
    location: str | None = Field(default=None, max_length=500)
    comments: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_time_range(self) -> "SchedulingRequestRespondRequest":
        """Valida que el rango horario sea consistente."""
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time")
        return self


class SchedulingRequestRejectRequest(BaseModel):
    """Payload para rechazar una solicitud con un motivo."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=1000)


class SchedulingRequestResponse(BaseModel):
    """Respuesta normalizada de una solicitud de agendamiento."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    internship_id: int | None
    purpose: PresentationPurposeEnum
    message: str | None
    preferred_dates: list[date]
    status: str  # Retornamos como string del status enum
    coordinator_id: int | None
    coordinator_response: str | None
    scheduled_date: date | None
    scheduled_start_time: time | None
    scheduled_end_time: time | None
    scheduled_modality: str | None
    scheduled_location: str | None
    presentation_id: int | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None

    student: UserCompactResponse | None = None
    coordinator: UserCompactResponse | None = None

    @field_validator("preferred_dates", mode="before")
    @classmethod
    def parse_preferred_dates(cls, v) -> list[date]:
        """Convierte preferred_dates almacenada como string/JSON en lista de date."""
        if isinstance(v, str):
            import json
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [date.fromisoformat(d) for d in parsed]
            except Exception:
                # Fallback por si acaso es formato texto simple separado por comas
                try:
                    return [date.fromisoformat(d.strip()) for d in v.split(",") if d.strip()]
                except Exception:
                    pass
        return v


class SchedulingConfigResponse(BaseModel):
    """Respuesta normalizada de la configuración de agendamiento."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    coordinator_id: int
    general_consultations_enabled: bool
    updated_at: datetime


class SchedulingConfigUpdateRequest(BaseModel):
    """Payload para actualizar la configuración de agendamiento."""

    model_config = ConfigDict(extra="forbid")

    general_consultations_enabled: bool

