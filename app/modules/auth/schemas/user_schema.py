"""Schemas Pydantic para operaciones y respuestas de usuario.

Este módulo define modelos de entrada (creación/actualización) y modelos de
salida (respuestas) relacionados con usuarios y su información de sesión.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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


class UserUpdateRequest(BaseModel):
    """Payload de solicitud para actualizar un usuario.

    Todos los campos son opcionales; si un campo no se envía, no se modifica.

    Attributes:
        first_name: Nuevo nombre(s) del usuario.
            Restricciones (si se envía): longitud mínima 1 y máxima 100.
        last_name: Nuevo apellido(s) del usuario.
            Restricciones (si se envía): longitud mínima 1 y máxima 100.
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

    is_active: bool | None = None


class UserResponse(BaseModel):
    """Modelo de respuesta con información de un usuario.

    Configurado con `from_attributes=True` para permitir la creación del schema
    a partir de instancias ORM.

    Attributes:
        id: Identificador entero del usuario.
        email: Correo electrónico del usuario.
        first_name: Nombre(s) del usuario.
        last_name: Apellido(s) del usuario.
        is_active: Indica si la cuenta está activa.
        is_verified: Indica si la cuenta ha sido verificada.
        created_at: Marca temporal de creación del usuario.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    first_name: str
    last_name: str
    is_active: bool
    is_verified: bool
    created_at: datetime


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
