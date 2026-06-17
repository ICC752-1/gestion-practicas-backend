"""Schemas HTTP para disponibilidad y reservas de agenda."""

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.scheduling.models.presentation_model import (
    PresentationPurposeEnum,
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
