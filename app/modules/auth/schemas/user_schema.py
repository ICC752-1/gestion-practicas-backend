"""Schemas Pydantic para operaciones y respuestas de usuario.

Este módulo define modelos de entrada (creación/actualización) y modelos de
salida (respuestas) relacionados con usuarios y su información de sesión.
"""

from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.auth.utils.normalization import normalize_phone, normalize_rut


class UserCreateRequest(BaseModel):
    """Payload de solicitud para crear un usuario.

    Attributes:
        email: Correo electrónico del usuario.
        password: Contraseña en texto plano.
            Restricciones: longitud mínima 8 y máxima 128 caracteres.
        first_name: Nombre(s) del usuario.
            Restricciones: longitud mínima 1 y máxima 100 caracteres.
        last_name: Apellido(s) del usuario.
            Restricciones: longitud mínima 1 y máxima 100 caracteres.
        rut: Identificador RUT del usuario.
            Restricciones: longitud máxima 100 caracteres.
        degree: Carrera o grado academico del usuario (opcional).
        cod_degree: Codigo interno de la carrera (opcional).
        sexo: Identificador de genero del usuario (opcional).
        phone: Telefono de contacto del usuario (opcional).
        profession: Profesion del usuario (opcional).
        position: Cargo del usuario (opcional).
        departament: Departamento del usuario (opcional).
        sup_phone: Telefono del supervisor (opcional).
    """

    email: EmailStr

    password: str = Field(
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

    rut: str = Field(
        min_length=1,
        max_length=100,
    )

    degree: str | None = Field(default=None, max_length=255)
    cod_degree: str | None = Field(default=None, max_length=100)
    sexo: Literal["Femenino", "Masculino", "Otro", "No definido"] | None = None
    phone: str | None = Field(default=None, max_length=100)
    profession: str | None = Field(default=None, max_length=100)
    position: str | None = Field(default=None, max_length=100)
    departament: str | None = Field(default=None, max_length=100)
    sup_phone: str | None = Field(default=None, max_length=100)
    role_ids: list[int] = Field(default_factory=list)

    @field_validator("rut")
    @classmethod
    def _normalize_rut(cls, value: str) -> str:
        return normalize_rut(value)

    @field_validator("phone", "sup_phone")
    @classmethod
    def _normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_phone(value)


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
    degree: str | None = Field(default=None, min_length=1, max_length=255)
    cod_degree: str | None = Field(default=None, min_length=1, max_length=100)
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
        degree: Carrera o grado academico del usuario.
        cod_degree: Codigo interno de la carrera.
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
    degree: str | None
    cod_degree: str | None
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


class UserAdminResponse(UserResponse):
    """Respuesta administrativa con roles actuales del usuario."""

    roles: list[str]


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
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    first_name: str
    last_name: str
    roles: list[str]
