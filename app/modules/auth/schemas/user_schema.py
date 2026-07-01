"""Schemas Pydantic para operaciones y respuestas de usuario.

Este módulo define modelos de entrada (creación/actualización) y modelos de
salida (respuestas) relacionados con usuarios y su información de sesión.
"""

from datetime import datetime

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.modules.internships.models.internship_model import PracticeTypeEnum
from app.modules.auth.utils.enrollment import parse_student_enrollment
from app.modules.auth.utils.normalization import normalize_phone, normalize_rut


class UserCreateRequest(BaseModel):
    """Payload de solicitud para crear un usuario.

    Attributes:
        email: Correo electrónico del usuario.
        password: Contraseña inicial opcional para compatibilidad.
            Si no se entrega, el backend genera una credencial interna aleatoria
            y el usuario define su contraseña mediante enlace de activación.
        first_name: Nombre(s) del usuario.
            Restricciones: longitud mínima 1 y máxima 100 caracteres.
        last_name: Apellido(s) del usuario.
            Restricciones: longitud mínima 1 y máxima 100 caracteres.
        rut: Identificador RUT del usuario para cuentas no estudiantiles.
        enrollment: Matrícula institucional para cuentas estudiantiles.
        degree: Carrera o grado academico del usuario (opcional).
        cod_degree: Codigo interno de la carrera (opcional).
        admission_year: Año de ingreso del estudiante (opcional).
        sexo: Identificador de genero del usuario (opcional).
        phone: Telefono de contacto del usuario (opcional).
        profession: Profesion del usuario (opcional).
        position: Cargo del usuario (opcional).
        departament: Departamento del usuario (opcional).
        sup_phone: Telefono del supervisor (opcional).
    """

    email: EmailStr

    password: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
    )

    first_name: str = Field(
        min_length=1,
        max_length=100,
    )

    last_name: str = Field(
        min_length=1,
        max_length=100,
    )

    rut: str | None = Field(default=None, min_length=1, max_length=100)
    enrollment: str | None = Field(default=None, min_length=1, max_length=32)

    degree: str | None = Field(default=None, max_length=255)
    cod_degree: str | None = Field(default=None, max_length=100)
    admission_year: int | None = Field(default=None, ge=1900, le=2100)
    sexo: Literal["Femenino", "Masculino", "Otro", "No definido"] | None = None
    phone: str | None = Field(default=None, max_length=100)
    profession: str | None = Field(default=None, max_length=100)
    position: str | None = Field(default=None, max_length=100)
    departament: str | None = Field(default=None, max_length=100)
    sup_phone: str | None = Field(default=None, max_length=100)
    role_ids: list[int] = Field(default_factory=list)

    @field_validator("rut")
    @classmethod
    def _normalize_rut(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_rut(value)

    @field_validator("phone", "sup_phone")
    @classmethod
    def _normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_phone(value)

    @model_validator(mode="after")
    def _derive_student_identity(self) -> "UserCreateRequest":
        if self.enrollment is not None:
            parsed = parse_student_enrollment(self.enrollment)
            if self.rut is not None and self.rut != parsed.rut:
                raise ValueError("La matrícula no coincide con el RUT informado")
            if (
                self.admission_year is not None
                and self.admission_year != parsed.admission_year
            ):
                raise ValueError(
                    "La matrícula no coincide con el año de ingreso informado"
                )
            self.enrollment = parsed.value
            self.rut = parsed.rut
            self.admission_year = parsed.admission_year

        if self.rut is None:
            raise ValueError("Debe informar un RUT o una matrícula")

        return self


class UserUpdateRequest(BaseModel):
    """Payload de solicitud para actualizar un usuario.

    Todos los campos son opcionales; si un campo no se envía, no se modifica.

    Attributes:
        first_name: Nuevo nombre(s) del usuario.
            Restricciones (si se envía): longitud mínima 1 y máxima 100.
        last_name: Nuevo apellido(s) del usuario.
            Restricciones (si se envía): longitud mínima 1 y máxima 100.
        rut: RUT del usuario.
        degree: Carrera o grado academico del usuario.
        cod_degree: Codigo interno de la carrera.
        admission_year: Año de ingreso del estudiante.
        sexo: Identificador de genero del usuario.
        phone: Telefono de contacto del usuario.
        profession: Profesion del usuario.
        position: Cargo del usuario.
        departament: Departamento del usuario.
        sup_phone: Telefono del supervisor.
        is_active: Estado de activación de la cuenta.
    """

    first_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    last_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    rut: str | None = Field(default=None, min_length=1, max_length=100)
    enrollment: str | None = Field(default=None, min_length=1, max_length=32)
    degree: str | None = Field(default=None, min_length=1, max_length=255)
    cod_degree: str | None = Field(default=None, min_length=1, max_length=100)
    admission_year: int | None = Field(default=None, ge=1900, le=2100)
    sexo: Literal["Femenino", "Masculino", "Otro", "No definido"] | None = None
    phone: str | None = Field(default=None, min_length=1, max_length=100)
    profession: str | None = Field(default=None, min_length=1, max_length=100)
    position: str | None = Field(default=None, min_length=1, max_length=100)
    departament: str | None = Field(default=None, min_length=1, max_length=100)
    sup_phone: str | None = Field(default=None, min_length=1, max_length=100)
    
    is_active: bool | None = None

    @field_validator("rut")
    @classmethod
    def _normalize_update_rut(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_rut(value)

    @field_validator("phone", "sup_phone")
    @classmethod
    def _normalize_update_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_phone(value)

    @model_validator(mode="after")
    def _derive_updated_student_identity(self) -> "UserUpdateRequest":
        if self.enrollment is None:
            return self

        parsed = parse_student_enrollment(self.enrollment)
        if self.rut is not None and self.rut != parsed.rut:
            raise ValueError("La matrícula no coincide con el RUT informado")
        if (
            self.admission_year is not None
            and self.admission_year != parsed.admission_year
        ):
            raise ValueError(
                "La matrícula no coincide con el año de ingreso informado"
            )

        self.enrollment = parsed.value
        self.rut = parsed.rut
        self.admission_year = parsed.admission_year
        return self


class UserResponse(BaseModel):
    """Modelo de respuesta con información de un usuario.

    Configurado con `from_attributes=True` para permitir la creación del schema
    a partir de instancias ORM.

    Attributes:
        id: Identificador entero del usuario.
        email: Correo electrónico del usuario.
        first_name: Nombre(s) del usuario.
        last_name: Apellido(s) del usuario.
        rut: Identificador RUT del usuario.
        enrollment: Matrícula institucional del estudiante.
        degree: Carrera o grado academico del usuario.
        cod_degree: Codigo interno de la carrera.
        admission_year: Año de ingreso del estudiante.
        sexo: Identificador de genero del usuario.
        phone: Telefono de contacto del usuario.
        profession: Profesion del usuario.
        position: Cargo del usuario.
        departament: Departamento del usuario.
        sup_phone: Telefono del supervisor.
        is_active: Indica si la cuenta está activa.
        is_verified: Indica si la cuenta ha sido verificada.
        must_change_password: Indica si debe reemplazar la credencial temporal.
        created_at: Marca temporal de creación del usuario.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    first_name: str
    last_name: str
    rut: str
    enrollment: str | None = None
    degree: str | None
    cod_degree: str | None
    admission_year: int | None
    sexo: str | None
    phone: str | None
    profession: str | None
    position: str | None
    departament: str | None
    sup_phone: str | None
    is_active: bool
    is_verified: bool
    must_change_password: bool = False
    created_at: datetime


class StudentPracticeProgressItem(BaseModel):
    """Estado académico de una etapa del plan de prácticas."""

    stage: Literal["practice_1", "practice_2", "final_option"]
    label: str
    type: PracticeTypeEnum | None = None
    available_types: list[PracticeTypeEnum] = Field(default_factory=list)
    requirement_status: str
    display_status: str
    internship_id: int | None = None
    request_status: str | None = None
    completion_status: str | None = None
    final_result: str | None = None
    is_current: bool = False
    is_completed: bool = False


class StudentAcademicProgressResponse(BaseModel):
    """Resumen del avance académico de un estudiante en sus prácticas."""

    completed_count: int
    total_count: int
    current_type: PracticeTypeEnum | None = None
    current_label: str | None = None
    current_status: str | None = None
    items: list[StudentPracticeProgressItem]


class UserAdminResponse(UserResponse):
    """Respuesta administrativa con roles actuales del usuario."""

    roles: list[str]
    academic_progress: StudentAcademicProgressResponse | None = None


class UserListResponse(BaseModel):
    """Respuesta paginada para el panel de Superadmin."""

    items: list[UserAdminResponse]
    total: int
    limit: int
    offset: int


class CurrentUserResponse(BaseModel):
    """Modelo de respuesta para el usuario autenticado actualmente.

    Incluye los roles asociados al usuario para facilitar autorizaciones en
    cliente o en capas superiores.

    Attributes:
        id: Identificador entero del usuario.
        email: Correo electrónico del usuario.
        first_name: Nombre(s) del usuario.
        last_name: Apellido(s) del usuario.
        roles: Lista de nombres de roles asociados.
        degree: Carrera o grado academico del usuario.
        cod_degree: Codigo interno de la carrera.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    first_name: str
    last_name: str
    roles: list[str]
    degree: str | None = None
    cod_degree: str | None = None
    enrollment: str | None = None
    admission_year: int | None = None
