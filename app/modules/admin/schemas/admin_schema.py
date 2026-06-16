"""Schemas HTTP del modulo admin.

Este modulo define los contratos de salida utilizados por los endpoints
administrativos orientados a `Encargado de practica` y `Director de carrera`.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr

Modality = Literal["Presencial", "Remoto", "Híbrido"]
AdminInternshipStatusFilter = Literal[
    "submitted",
    "in_review",
    "approved",
    "rejected",
]


class AdminSummaryByStatusItem(BaseModel):
    """Representa un conteo agregado de practicas por estado.

    Attributes:
        status  : Nombre del estado de practica.
        total   : Cantidad total de practicas en dicho estado.
    """

    status: str
    total: int


class AdminSummaryResponse(BaseModel):
    """Respuesta de resumen administrativo del sistema.

    Attributes:
        total_students        : Cantidad total de estudiantes registrados.
        total_internships     : Cantidad total de practicas registradas.
        internships_by_status : Conteo agregado de practicas por estado actual.
    """

    total_students: int
    total_internships: int
    internships_by_status: list[AdminSummaryByStatusItem]


class AdminStudentListItem(BaseModel):
    """Representa un estudiante dentro del listado administrativo.

    Attributes:
        id         : Identificador entero del estudiante.
        email      : Correo electronico del estudiante.
        first_name : Nombre del estudiante.
        last_name  : Apellido del estudiante.
        rut        : RUT del estudiante.
        is_active  : Indica si la cuenta esta activa.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    first_name: str
    last_name: str
    rut: str
    is_active: bool


class AdminInternshipStatusInfo(BaseModel):
    """Representa el estado actual de una practica.

    Attributes:
        id          : Identificador entero del estado.
        title       : Nombre corto del estado.
        description : Descripcion funcional del estado.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str


class AdminInternshipStudentInfo(BaseModel):
    """Representa al estudiante asociado a una practica.

    Attributes:
        id         : Identificador entero del estudiante.
        email      : Correo electronico del estudiante.
        first_name : Nombre del estudiante.
        last_name  : Apellido del estudiante.
        rut        : RUT del estudiante.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    first_name: str
    last_name: str
    rut: str


class AdminInternshipListItem(BaseModel):
    """Representa una practica dentro del listado administrativo.

    Attributes:
        id          : Identificador entero de la practica.
        org_name    : Nombre de la organizacion.
        city        : Ciudad de la organizacion.
        start_date  : Fecha de inicio de la practica.
        end_date    : Fecha de termino de la practica.
        upload_date : Fecha de registro de la practica.
        user_id     : Identificador del estudiante propietario.
        student     : Informacion basica del estudiante asociado.
        status      : Estado actual de la practica, si existe.
        is_cancelled: Indica si la practica fue anulada logicamente.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    org_name: str
    city: str
    start_date: date
    end_date: date
    upload_date: datetime
    user_id: int | None
    student: AdminInternshipStudentInfo | None
    status: AdminInternshipStatusInfo | None
    is_cancelled: bool


class AdminInternshipDetailResponse(BaseModel):
    """Representa el detalle administrativo completo de una practica.

    Attributes:
        id                  : Identificador entero de la practica.
        org_name            : Nombre de la organizacion donde se realiza la practica.
        sector              : Sector o rubro de la organizacion.
        address             : Direccion principal de la organizacion.
        city                : Ciudad donde se ubica la organizacion.
        org_phone           : Telefono de contacto de la organizacion, si existe.
        web                 : Sitio web de la organizacion, si existe.
        start_date          : Fecha de inicio de la practica.
        end_date            : Fecha de termino de la practica.
        schedule            : Horario definido para la practica.
        days                : Dias en que se realizara la practica.
        modality            : Modalidad de la practica.
        internship_address  : Direccion especifica donde se ejecuta la practica.
        act_description     : Descripcion de actividades a realizar.
        ben_description     : Descripcion del beneficio o aporte esperado.
        amount              : Monto asociado a la practica, si corresponde.
        upload_date         : Fecha y hora de registro de la practica.
        status_id           : Identificador del estado actual, si existe.
        user_id             : Identificador del estudiante propietario.
        student             : Informacion basica del estudiante asociado.
        status              : Estado actual de la practica, si existe.
        is_cancelled        : Indica si la practica fue anulada logicamente.
        cancelled_at        : Fecha de anulacion, si existe.
        cancellation_reason : Motivo de anulacion, si existe.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    org_name: str
    sector: str
    address: str
    city: str
    org_phone: str | None
    web: str | None
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
    student: AdminInternshipStudentInfo | None
    status: AdminInternshipStatusInfo | None
    is_cancelled: bool
    cancelled_at: datetime | None
    cancellation_reason: str | None


StudentInternshipRequirementType = Literal[
    "Práctica de Estudio I",
    "Práctica de Estudio II",
    "Tesis",
    "Práctica Controlada",
]
StudentInternshipRequirementStatus = Literal[
    "Pendiente",
    "Habilitada",
    "En revisión",
    "Aprobada",
    "Rechazada",
]


class AdminStudentInternshipRequirementItem(BaseModel):
    """Representa un requisito de práctica asociado a un estudiante."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    type: StudentInternshipRequirementType
    status: StudentInternshipRequirementStatus
    status_updated_at: datetime | None
    status_updated_by: int | None
    created_at: datetime
    updated_at: datetime


class AdminUpdateStudentInternshipRequirementStatusRequest(BaseModel):
    """Payload para actualizar el estado de un requisito de práctica."""

    status: StudentInternshipRequirementStatus


RegistrationRequirementType = Literal["school_insurance", "induction"]


class AdminRegistrationRequirementItem(BaseModel):
    """Representa un prerrequisito institucional asociado a un estudiante."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    requirement: RegistrationRequirementType
    is_completed: bool
    completed_at: datetime | None
    updated_by: int | None


class AdminUpdateSchoolInsuranceRequest(BaseModel):
    """Payload administrativo para registrar el seguro escolar vigente."""

    is_completed: bool
