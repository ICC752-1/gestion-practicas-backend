"""Schemas Pydantic para tokens y validación.

Este módulo define modelos de respuesta y payload relacionados con tokens JWT
y la verificación de su validez.
"""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, EmailStr

class TokenResponse(BaseModel):
    """Respuesta estándar con tokens de acceso y refresco.

    Attributes:
        access_token: Token de acceso.
        refresh_token: Token de refresco para renovar el acceso.
        token_type: Tipo de token (por defecto, ``"bearer"``).
    """

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"

class TokenPayload(BaseModel):
    """Payload típico contenido en un token de acceso.

    Attributes:
        sub: Identificador del sujeto (usuario) del token.
        email: Correo electrónico del usuario.
        roles: Lista de roles asociados al usuario.
        type: Tipo de token, siempre ``"access"``.
        exp: Fecha/hora de expiración del token.
    """

    sub: str
    email: EmailStr
    roles: list[str]
    type: Literal["access"]
    exp: datetime

class RefreshTokenPayload(BaseModel):
    """Payload típico contenido en un refresh token.

    Attributes:
        sub: Identificador del sujeto (usuario) del token.
        jti: Identificador único del refresh token.
        type: Tipo de token, siempre ``"refresh"``.
        exp: Fecha/hora de expiración del refresh token.
    """

    sub: str
    jti: str
    type: Literal["refresh"]
    exp: datetime

class TokenValidationResponse(BaseModel):
    """Resultado de validación de un token.

    Attributes:
        valid: Indica si el token es válido.
        expired: Indica si el token está expirado.
    """

    valid: bool
    expired: bool
    
