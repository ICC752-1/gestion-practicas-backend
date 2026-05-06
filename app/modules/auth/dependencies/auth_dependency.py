"""Dependencias de autenticación y autorización.

Este módulo define dependencias de FastAPI para extraer el usuario autenticado
desde un token OAuth2 (Bearer) y validar su estado.
"""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.user_model import User
from app.modules.auth.repositories.user_repository import UserRepository
from app.core.database.database import get_db
from app.modules.auth.services.token_service import TokenService


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")
logger = logging.getLogger(__name__)

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Obtiene y valida el usuario autenticado a partir de un token Bearer.

    El flujo de validación incluye:

    - Decodificar el token con `TokenService`.
    - Verificar que el payload contenga `sub` (identificador del usuario).
    - Consultar el usuario en base de datos.
    - Validar que el usuario exista y esté activo.

    Args:
        token: Token Bearer provisto por `OAuth2PasswordBearer`.
        db: Sesión asíncrona inyectada por `get_db`.

    Returns:
        La entidad de usuario autenticado.

    Raises:
        HTTPException: Con código 401 si el token es inválido/expiró, el payload
            es inválido, el usuario no existe o está inactivo.
    """

    token_service = TokenService()

    try:
        payload = token_service.decode_token(token)

    except ValueError as exc:
        if str(exc) == "Token ha expirado":
            logger.warning("JWT token expired")
        else:
            logger.warning("Invalid JWT token")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    except Exception:
        logger.error("Unexpected error while decoding JWT token", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user_id = payload.get("sub")

    if not user_id:
        logger.warning("JWT token payload is missing subject")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        logger.warning("JWT token subject is invalid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    user_repository = UserRepository(db)
    user = await user_repository.get_user_by_id(user_id_int)

    if not user:
        logger.warning("User from JWT token was not found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if not user.is_active:
        logger.warning("Inactive user attempted to access a protected endpoint")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user"
        )
    
    return user
