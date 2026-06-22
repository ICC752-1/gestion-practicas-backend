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
    owner: "UserCompactResponse | None" = None


class UserCompactResponse(BaseModel):
    """Información compacta de un usuario (estudiante o coordinador)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str
    role_name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _compute_role_name(cls, data):
        """Mapea el rol del ORM a una etiqueta de visualización consistente.

        Cuando la instancia proviene de un objeto ORM ``User`` (vía
        ``from_attributes=True``), inspecciona ``user.roles`` y traduce el primer
        rol administrativo a su etiqueta de display: ``Director de carrera`` →
        ``Director`` y ``Encargado de practica`` → ``Coordinador``. Si ``roles``
        no está cargado o no hay rol administrativo, deja ``role_name`` en
        ``None``.
        """

        if isinstance(data, dict):
            return data

        from sqlalchemy import inspect
        state = inspect(data, raiseerr=False)
        roles = None
        if state is not None:
            if "roles" not in state.unloaded:
                roles = data.roles
        else:
            roles = getattr(data, "roles", None)

        role_name = _resolve_display_role(roles) if roles is not None else None

        return {
            "id": data.id,
            "first_name": data.first_name,
            "last_name": data.last_name,
            "email": data.email,
            "role_name": role_name,
        }


def _resolve_display_role(roles) -> str | None:
    """Traduce la lista de ``UserRole`` del ORM a una etiqueta de display."""

    role_mapping = {
        "Director de carrera": "Director",
        "Encargado de practica": "Coordinador",
    }

    from sqlalchemy import inspect

    for user_role in roles or []:
        state = inspect(user_role, raiseerr=False)
        role = None
        if state is not None:
            if "role" not in state.unloaded:
                role = getattr(user_role, "role", None)
        else:
            role = getattr(user_role, "role", None)

        if role is not None:
            name = getattr(role, "name", None)
            if name in role_mapping:
                return role_mapping[name]

    return None


PresentationSlotResponse.model_rebuild()


class SchedulingRequestCreateRequest(BaseModel):
    """Payload para crear una solicitud de agendamiento."""

    model_config = ConfigDict(extra="forbid")

    purpose: PresentationPurposeEnum
    internship_id: int | None = Field(default=None, gt=0)
    target_coordinator_id: int | None = Field(default=None, gt=0)
    message: str | None = Field(default=None, max_length=1000)
    preferred_dates: list[date] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def validate_purpose_requirements(self) -> "SchedulingRequestCreateRequest":
        """Valida campos requeridos según el propósito del agendamiento.

        - ``internship_id`` es obligatorio para presentaciones finales.
        - ``target_coordinator_id`` es obligatorio para consultas generales.
        """

        if (
            self.purpose == PresentationPurposeEnum.final_presentation
            and not self.internship_id
        ):
            raise ValueError("internship_id es requerido para presentaciones finales")

        if (
            self.purpose == PresentationPurposeEnum.general_consultation
            and not self.target_coordinator_id
        ):
            raise ValueError(
                "target_coordinator_id es requerido para consultas generales"
            )

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
    target_coordinator_id: int | None
    resolved_by_role: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None

    student: UserCompactResponse | None = None
    coordinator: UserCompactResponse | None = None
    target_coordinator: UserCompactResponse | None = None

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
    internship_applications_disabled: bool
    updated_at: datetime


class SchedulingConfigUpdateRequest(BaseModel):
    """Payload para actualizar la configuración de agendamiento.

    Ambos campos son opcionales para permitir actualizaciones parciales, pero al
    menos uno debe estar definido. ``internship_applications_disabled`` sólo puede
    ser modificado por el ``Director de carrera`` (validado en el servicio).
    """

    model_config = ConfigDict(extra="forbid")

    general_consultations_enabled: bool | None = None
    internship_applications_disabled: bool | None = None

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "SchedulingConfigUpdateRequest":
        """Valida que al menos uno de los campos esté definido."""

        if (
            self.general_consultations_enabled is None
            and self.internship_applications_disabled is None
        ):
            raise ValueError(
                "Debes indicar al menos un campo: general_consultations_enabled "
                "o internship_applications_disabled"
            )

        return self


class DirectSchedulingRequest(BaseModel):
    """Payload para agendar directamente una presentación final sin solicitud previa."""

    model_config = ConfigDict(extra="forbid")

    internship_id: int = Field(gt=0)
    date: date
    start_time: time
    end_time: time
    modality: Modality
    location: str | None = Field(default=None, max_length=500)
    comments: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_time_range(self) -> "DirectSchedulingRequest":
        """Valida que el rango horario sea consistente."""
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time")
        return self


