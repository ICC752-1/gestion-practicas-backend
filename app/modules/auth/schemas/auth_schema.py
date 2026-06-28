"""Schemas Pydantic para solicitudes de autenticación.

Este módulo agrupa modelos de entrada usados por los endpoints de autenticación
y gestión de sesión (login, refresh, logout y operaciones de contraseña).
"""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.modules.auth.utils.normalization import normalize_phone

class LoginRequest(BaseModel):
    """Payload de solicitud para iniciar sesión.

    Attributes:
        email: Correo electrónico del usuario.
        password: Contraseña en texto plano.
            Restricciones: longitud mínima 8 y máxima 128 caracteres.
    """

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class CompleteTemporaryPasswordRequest(BaseModel):
    """Payload para reemplazar una credencial temporal de un solo uso."""

    email: EmailStr
    temporary_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class ActivateAccountRequest(BaseModel):
    """Payload para activar una cuenta mediante enlace de un solo uso."""

    token: str = Field(min_length=32, max_length=512)
    new_password: str = Field(min_length=8, max_length=128)
    phone: str | None = Field(default=None, max_length=100)
    sexo: Literal["Femenino", "Masculino", "Otro", "No definido"] | None = None

    @field_validator("phone")
    @classmethod
    def _normalize_optional_phone(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return normalize_phone(value)


class ActivationAccountInfoResponse(BaseModel):
    """Datos mínimos de una cuenta pendiente de activación."""

    email: EmailStr
    first_name: str
    last_name: str
    roles: list[str]
    enrollment: str | None = None
    admission_year: int | None = None
    phone: str | None = None
    sexo: str | None = None

class RefreshTokenRequest(BaseModel):
    """Payload de solicitud para renovar tokens de acceso.

    Attributes:
        refresh_token: Token de refresco emitido previamente.
    """

    refresh_token: str | None = None

class ChangePasswordRequest(BaseModel):
    """Payload de solicitud para cambiar la contraseña del usuario.

    Attributes:
        old_password: Contraseña actual del usuario.
            Restricciones: longitud mínima 8 y máxima 128 caracteres.
        new_password: Nueva contraseña que se desea establecer.
            Restricciones: longitud mínima 8 y máxima 128 caracteres.
    """

    old_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

class ForgotPasswordRequest(BaseModel):
    """Payload de solicitud para iniciar el flujo de recuperación de contraseña.

    Attributes:
        email: Correo electrónico asociado a la cuenta.
    """

    email: EmailStr

class ResetPasswordRequest(BaseModel):
    """Payload de solicitud para restablecer la contraseña.

    Attributes:
        token: Token de restablecimiento (p. ej. enviado por correo).
        new_password: Nueva contraseña que se desea establecer.
            Restricciones: longitud mínima 8 y máxima 128 caracteres.
    """

    token: str
    new_password: str = Field(min_length=8, max_length=128)

class LogoutRequest(BaseModel):
    """Payload de solicitud para cerrar sesión.

    Attributes:
        refresh_token: Token de refresco que se desea invalidar.
    """

    refresh_token: str | None = None
