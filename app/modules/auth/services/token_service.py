"""Servicios de creación y validación de tokens.

Este módulo define `TokenService`, responsable de generar tokens JWT (access y
refresh) y de decodificarlos/validarlos usando la configuración de la
aplicación.
"""

from datetime import datetime, UTC, timedelta
from typing import Any
import jwt

from app.core.config import config


class TokenService:
    """Genera y decodifica tokens JWT para autenticación.

    Los tiempos de expiración y el secreto/algoritmo se obtienen desde `config`.
    """

    def create_access_token(self, subject:str, email:str, roles:list[str]) -> str:
        """Crea un access token (JWT) con información del usuario.

        El token incluye los claims: `sub`, `email`, `roles` y `exp`.

        Args:
            subject: Identificador del sujeto (normalmente el ID del usuario).
            email: Correo electrónico del usuario.
            roles: Lista de nombres de roles asociados.

        Returns:
            Token JWT codificado como cadena.
        """

        expire = datetime.now(UTC) + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)

        payload: dict[str, Any] = {
            "sub": subject,
            "email": email,
            "roles": roles,
            "exp": expire,
        }
        
        return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)  # pyright: ignore[reportUnknownMemberType]
    
    def create_refresh_token(self, subject:str) -> str:
        """Crea un refresh token (JWT) para renovar tokens de acceso.

        El token incluye los claims: `sub` y `exp`.

        Args:
            subject: Identificador del sujeto (normalmente el ID del usuario).

        Returns:
            Token JWT codificado como cadena.
        """

        expire = datetime.now(UTC) + timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)

        payload: dict[str, Any] = {
            "sub": subject,
            "exp": expire,
        }
        
        return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)  # pyright: ignore[reportUnknownMemberType]
    
    def decode_token(self, token:str) -> dict[str, Any]:
        """Decodifica y valida un token JWT.

        Args:
            token: Token JWT codificado.

        Returns:
            Diccionario con el payload decodificado.

        Raises:
            ValueError: Si el token expiró o es inválido.
        """

        try:
            payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])  # pyright: ignore[reportUnknownMemberType]
            return payload
        
        except jwt.ExpiredSignatureError:
            raise ValueError("Token ha expirado")
        
        except jwt.InvalidTokenError:
            raise ValueError("Token inválido")