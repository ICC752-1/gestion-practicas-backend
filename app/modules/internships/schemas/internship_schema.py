"""Schemas Pydantic para solicitudes y respuestas de practicas.

Este modulo centraliza los contratos HTTP del modulo `internships`. Los schemas
validan payloads de entrada y definen respuestas serializables a partir de
instancias ORM.
"""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.modules.internships.models.internship_model import (
    PracticePeriodEnum,
    PracticeTypeEnum,
)


Modality = Literal["Presencial", "Remoto", "Híbrido"]
DashboardInternshipStatus = Literal["submitted", "in_review", "approved", "rejected"]


class InternshipCreateRequest(BaseModel):
    """Payload para crear una practica.

    El campo ``has_school_insurance`` fue eliminado deliberadamente:
    el backend ahora computa el cumplimiento del seguro escolar a partir
    de los registros internos del estudiante y las excepciones vigentes.
    """

    model_config = ConfigDict(extra="forbid")

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


class InternshipTrackingActorResponse(BaseModel):
    """Informacion basica del usuario que ejecuta una transicion."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    first_name: str
    last_name: str


class InternshipTrackingResponse(BaseModel):
    """Respuesta con una entrada del historial de estados de una practica.

    Attributes:
        id: Identificador entero de la entrada de historial.
        internship_id: Identificador de la practica asociada.
        previous_status: Estado anterior, si existia.
        new_status: Estado nuevo asignado a la practica.
        actor: Usuario que ejecuto o disparo la transicion.
        reason: Motivo funcional de la transicion, si corresponde.
        changed_at: Fecha y hora de la transicion.
        metadata: Datos auxiliares de contexto.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    internship_id: int
    previous_status: CurrentStateResponse | None
    new_status: CurrentStateResponse
    actor: InternshipTrackingActorResponse | None
    reason: str | None
    changed_at: datetime
    metadata: dict[str, Any] | None = Field(
        default=None,
        validation_alias="metadata_json",
    )


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
        is_cancelled: Indica si la practica fue anulada logicamente.
        cancelled_at: Fecha y hora de anulacion logica, si existe.
        cancelled_by: Identificador del usuario que anulo la practica.
        cancellation_reason: Motivo funcional de la anulacion logica.
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
    is_cancelled: bool
    cancelled_at: datetime | None
    cancelled_by: int | None
    cancellation_reason: str | None

    exceptions: list["InternshipExceptionResponse"] = []


class InternshipAdminUpdateRequest(BaseModel):
    """Payload para edicion administrativa acotada de una practica."""

    model_config = ConfigDict(extra="forbid")

    reason: str
    org_name: str | None = None
    sector: str | None = None
    address: str | None = None
    city: str | None = None
    org_phone: str | None = None
    web: str | None = None
    supervisor_name: str | None = None
    supervisor_profession: str | None = None
    supervisor_position: str | None = None
    supervisor_department: str | None = None
    supervisor_email: EmailStr | None = None
    supervisor_phone: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    schedule: str | None = None
    days: str | None = None
    modality: Modality | None = None
    internship_address: str | None = None
    act_description: str | None = None
    ben_description: str | None = None
    amount: int | None = None


class InternshipCancelRequest(BaseModel):
    """Payload para anulacion logica de una practica."""

    model_config = ConfigDict(extra="forbid")

    reason: str


class InternshipCancelResponse(BaseModel):
    """Respuesta tras anular logicamente una practica."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_cancelled: bool
    cancelled_at: datetime | None
    cancelled_by: int | None
    cancellation_reason: str | None

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

class InternshipExceptionRequest(BaseModel):
    """Payload para registrar una excepcion administrativa.

    Attributes:
        rule: Regla de negocio que se exceptua. Valores habilitados:
            ``"school_insurance"``, ``"sequentiality"``,
            ``"sequentiality_thesis"``, ``"parallel_course"``.
        reason: Justificacion obligatoria de la excepcion. No puede
            estar vacia ni contener solo espacios en blanco.
    """

    rule: Literal[
        "school_insurance",
        "sequentiality",
        "sequentiality_thesis",
        "parallel_course",
    ] = Field(
        description="Regla de negocio exceptuada."
    )
    reason: str = Field(
        min_length=1,
        max_length=1000,
        description="Justificacion obligatoria de la excepcion.",
    )

    @model_validator(mode="after")
    def validate_reason_not_blank(self) -> "InternshipExceptionRequest":
        if not self.reason.strip():
            raise ValueError("El motivo de la excepción no puede estar vacío.")
        return self


class InternshipExceptionActorResponse(BaseModel):
    """Actor que autorizó la excepción."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    first_name: str
    last_name: str


class InternshipExceptionResponse(BaseModel):
    """Respuesta tras registrar o consultar una excepcion administrativa.

    Attributes:
        id: Identificador de la excepcion.
        internship_id: Practica asociada.
        rule: Regla exceptuada.
        reason: Justificacion registrada.
        authorized_by: Datos del usuario que autorizó la excepción.
        authorized_at: Timestamp de la autorizacion.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    internship_id: int
    rule: str
    reason: str
    authorized_by: InternshipExceptionActorResponse = Field(
        validation_alias="actor"
    )
    authorized_at: datetime


# ──────────────────────────────────────────────
# Schemas de Inducción Obligatoria
# ──────────────────────────────────────────────


class InductionVideoResponse(BaseModel):
    """Video embebible de una versión de contenido de inducción."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    video_url: str
    order: int


class InductionQuestionResponse(BaseModel):
    """Pregunta de cuestionario visible para el estudiante (sin respuesta)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    question_text: str
    options: dict
    order: int


class InductionContentVersionResponse(BaseModel):
    """Versión de contenido de inducción publicada y activa.

    Incluye videos y preguntas. El campo ``min_score`` permite al frontend
    informar al estudiante sobre el puntaje mínimo para aprobar.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    min_score: int
    videos: list[InductionVideoResponse] = []
    questions: list[InductionQuestionResponse] = []


class InductionAttemptRequest(BaseModel):
    """Payload para enviar las respuestas del cuestionario de inducción.

    Attributes:
        answers: Diccionario donde la clave es el ``id`` de la pregunta
            y el valor es la opción seleccionada por el estudiante.
    """

    answers: dict[int, str]


class InductionAttemptResponse(BaseModel):
    """Resultado de un intento de cuestionario de inducción.

    Attributes:
        id: Identificador del intento registrado.
        score: Puntaje obtenido (aciertos).
        passed: ``True`` si el puntaje alcanzó o superó el mínimo.
        attempted_at: Fecha y hora del intento.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    score: int
    passed: bool
    attempted_at: datetime


# ──────────────────────────────────────────────
# Schema de Elegibilidad para Registro
# ──────────────────────────────────────────────


class RegistrationEligibilityResponse(BaseModel):
    """Elegibilidad del estudiante para registrar una práctica.

    Attributes:
        has_school_insurance: ``True`` si el estudiante tiene registrado
            el cumplimiento del seguro escolar.
        has_induction: ``True`` si el estudiante aprobó el cuestionario
            de inducción obligatoria.
        has_school_insurance_exception: ``True`` si existe una excepción
            administrativa activa para seguro escolar en alguna práctica
            vigente del estudiante.
        has_approved_practice_1: ``True`` si el estudiante tiene al menos
            una Práctica de Estudio I en estado ``Aprobada``.
        sequentiality_blocked: ``True`` si el estudiante no tiene una
            Práctica de Estudio I aprobada (informativo, no bloquea).
        has_sequentiality_exception: ``True`` si existe una excepción
            administrativa activa de secuencialidad en alguna práctica
            del estudiante.
        blocked: ``True`` si existe algún bloqueo activo que impida
            el registro o aprobación.
        next_step: Texto descriptivo de la siguiente acción recomendada
            para el estudiante.
    """

    has_school_insurance: bool
    has_induction: bool
    has_school_insurance_exception: bool = False
    has_approved_practice_1: bool = False
    sequentiality_blocked: bool = False
    has_sequentiality_exception: bool = False
    blocked: bool
    next_step: str
