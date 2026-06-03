"""Schemas Pydantic para solicitudes y respuestas de practicas.

Este modulo centraliza los contratos HTTP del modulo `internships`. Los schemas
validan payloads de entrada y definen respuestas serializables a partir de
instancias ORM.
"""

from datetime import date, datetime
from typing import Literal

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.modules.internships.models.internship_model import (
    PracticePeriodEnum,
    PracticeTypeEnum,
)

Modality = Literal["Presencial", "Remoto", "Híbrido"]
DashboardInternshipStatus = Literal["submitted", "in_review", "approved", "rejected"]


class InternshipCreateRequest(BaseModel):
    """Payload para crear una practica.

    Attributes:
        org_name: Nombre de la organizacion donde se realiza la practica.
        sector: Sector o rubro de la organizacion.
        address: Direccion principal de la organizacion.
        city: Ciudad donde se ubica la organizacion.
        org_phone: Telefono de contacto de la organizacion, si existe.
        web: Sitio web de la organizacion, si existe.
        supervisor_name: Nombre completo del supervisor de practica.
        supervisor_profession: Profesion del supervisor de practica.
        supervisor_position: Cargo del supervisor de practica.
        supervisor_department: Departamento o seccion del supervisor.
        supervisor_email: Correo electronico del supervisor.
        supervisor_phone: Telefono del supervisor de practica.
        start_date: Fecha de inicio de la practica.
        end_date: Fecha de termino de la practica.
        schedule: Horario definido para la practica.
        days: Dias en que se realizara la practica.
        modality: Modalidad de la practica (`Presencial`, `Remoto` o
            `Híbrido`).
        internship_address: Direccion especifica donde se ejecutara la
            practica.
        internship_period: Periodo de la practica.
        internship_type: Tipo de practica.
        has_school_insurance: Indica si posee seguro escolar vigente.
        act_description: Descripcion de actividades a realizar.
        ben_description: Descripcion del beneficio o aporte esperado.
        amount: Monto asociado a la practica, si corresponde.
    """

    org_name: str = Field(min_length=1, max_length=255)
    sector: str = Field(min_length=1, max_length=255)
    address: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=255)
    org_phone: str | None = Field(default=None, max_length=255)
    web: str | None = Field(default=None, max_length=255)
    supervisor_name: str = Field(min_length=1, max_length=255)
    supervisor_profession: str = Field(min_length=1, max_length=255)
    supervisor_position: str = Field(min_length=1, max_length=255)
    supervisor_department: str = Field(min_length=1, max_length=255)
    supervisor_email: EmailStr
    supervisor_phone: str = Field(min_length=1, max_length=255)
    start_date: date
    end_date: date
    schedule: str = Field(min_length=1, max_length=255)
    days: str = Field(min_length=1, max_length=255)
    modality: Modality
    internship_address: str = Field(min_length=1, max_length=255)
    act_description: str = Field(min_length=1, max_length=255)
    ben_description: str = Field(min_length=1, max_length=255)
    amount: int | None = Field(default=None, ge=0)
    internship_period: PracticePeriodEnum
    internship_type: PracticeTypeEnum
    has_school_insurance: bool

    @model_validator(mode="after")
    def validate_date_range(self) -> "InternshipCreateRequest":
        """Valida que el rango de fechas sea consistente.

        Returns:
            La misma instancia validada.

        Raises:
            ValueError: Si `end_date` es anterior a `start_date`.
        """

        if self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date")

        return self

    @model_validator(mode="after")
    def validate_school_insurance(self) -> "InternshipCreateRequest":
        """Valida que el estudiante tenga el seguro escolar
        Garantiza que no se realicen practicas en el periodo estival ('Verano' o 'Invierno')
        sin el respaldo del seguro escolar obligatorio (D.S. 313)
        """
        is_seasonal_period = self.internship_period in (
            PracticePeriodEnum.summer,
            PracticePeriodEnum.winter,
        )
        if is_seasonal_period and not self.has_school_insurance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "field": "has_school_insurance",
                    "message": (
                        "No es posible registrar práctica estival sin respaldo "
                        "de seguro escolar vigente (D.S. 313)"
                    ),
                },
            )
        return self


class CurrentStateResponse(BaseModel):
    """Respuesta con informacion de un estado de practica.

    Attributes:
        id: Identificador entero del estado.
        title: Nombre corto del estado.
        description: Descripcion funcional del estado.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str


class InternshipDashboardStudentResponse(BaseModel):
    """Informacion basica del estudiante para el dashboard coordinador."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    first_name: str
    last_name: str
    rut: str
    degree: str | None


class InternshipDashboardListItem(BaseModel):
    """Practica resumida para listados del dashboard coordinador."""

    id: int
    org_name: str
    city: str
    internship_type: PracticeTypeEnum
    start_date: date
    end_date: date
    upload_date: datetime
    status: DashboardInternshipStatus
    status_label: str
    student: InternshipDashboardStudentResponse | None


class InternshipDashboardStatsResponse(BaseModel):
    """Conteos agregados de practicas para el dashboard coordinador."""

    total: int
    submitted: int
    in_review: int
    approved: int
    rejected: int


class InternshipResponse(BaseModel):
    """Respuesta con informacion de una practica.

    Configurado con `from_attributes=True` para permitir serializar instancias
    ORM de `Internship`.

    Attributes:
        id: Identificador entero de la practica.
        org_name: Nombre de la organizacion donde se realiza la practica.
        sector: Sector o rubro de la organizacion.
        address: Direccion principal de la organizacion.
        city: Ciudad donde se ubica la organizacion.
        org_phone: Telefono de contacto de la organizacion, si existe.
        web: Sitio web de la organizacion, si existe.
        supervisor_name: Nombre completo del supervisor de practica.
        supervisor_profession: Profesion del supervisor de practica.
        supervisor_position: Cargo del supervisor de practica.
        supervisor_department: Departamento o seccion del supervisor.
        supervisor_email: Correo electronico del supervisor.
        supervisor_phone: Telefono del supervisor de practica.
        start_date: Fecha de inicio de la practica.
        end_date: Fecha de termino de la practica.
        schedule: Horario definido para la practica.
        days: Dias en que se realizara la practica.
        modality: Modalidad de la practica.
        internship_address: Direccion especifica donde se ejecutara la
            practica.
        act_description: Descripcion de actividades a realizar.
        ben_description: Descripcion del beneficio o aporte esperado.
        amount: Monto asociado a la practica, si corresponde.
        upload_date: Fecha y hora de registro de la practica.
        status_id: Identificador del estado actual, si existe.
        user_id: Identificador del estudiante propietario de la practica.
        internship_address: Direccion especifica donde se ejecutara la
            practica.
        internship_period: Periodo de la practica.
        internship_type: Tipo de practica.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    org_name: str
    sector: str
    address: str
    city: str
    org_phone: str | None
    web: str | None
    supervisor_name: str
    supervisor_profession: str
    supervisor_position: str
    supervisor_department: str
    supervisor_email: EmailStr
    supervisor_phone: str
    start_date: date
    end_date: date
    schedule: str
    days: str
    modality: Modality
    internship_address: str
    act_description: str
    ben_description: str
    amount: int | None
    upload_date: datetime
    status_id: int | None
    user_id: int | None
    internship_period: PracticePeriodEnum
    internship_type: PracticeTypeEnum
    has_school_insurance: bool

class InternshipActionRequest(BaseModel):
    """Payload para acciones de transición de estado.

    Attributes:
        comment: Comentario obligatorio en rechazo y derivación.
    """
    comment: str | None = Field(default=None, max_length=1000)


class InternshipActionResponse(BaseModel):
    """Respuesta tras ejecutar una acción de transición."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status_id: int | None
    comment: str | None