"""Schemas Pydantic para solicitudes de autenticación.

Este módulo agrupa modelos de entrada usados por los endpoints de autenticación
y gestión de sesión (login, refresh, logout y operaciones de contraseña).
"""

from pydantic import BaseModel, EmailStr, Field

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

class RefreshTokenRequest(BaseModel):
    """Payload de solicitud para renovar tokens de acceso.

    Attributes:
        refresh_token: Token de refresco emitido previamente. En sesiones
            OAuth puede omitirse si viene en cookie HttpOnly.
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
        refresh_token: Token de refresco que se desea invalidar. En sesiones
            OAuth puede omitirse si viene en cookie HttpOnly.
    """

    refresh_token: str | None = None
