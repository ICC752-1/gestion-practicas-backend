"""Dependencias de autenticación y autorización.

Este módulo define dependencias de FastAPI para extraer el usuario autenticado
desde un token OAuth2 (Bearer) y validar su estado.
"""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models.user_model import User
from app.modules.auth.repositories.user_repository import UserRepository
from app.core.database.database import get_db
from app.modules.auth.services.token_service import TokenService


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
logger = logging.getLogger(__name__)


def _credentials_exception(detail: str = "Invalid or expired token") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


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

        raise _credentials_exception()

    except Exception:
        logger.error("Unexpected error while decoding JWT token", exc_info=True)
        raise _credentials_exception()

    if payload.get("type") != "access":
        logger.warning("JWT token type is not valid for authentication")
        raise _credentials_exception("Invalid token type")
    
    user_id = payload.get("sub")

    if not user_id:
        logger.warning("JWT token payload is missing subject")
        raise _credentials_exception("Invalid token payload")

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        logger.warning("JWT token subject is invalid")
        raise _credentials_exception("Invalid token payload")

    user_repository = UserRepository(db)
    user = await user_repository.get_user_by_id(user_id_int)

    if not user:
        logger.warning("User from JWT token was not found")
        raise _credentials_exception("User not found")

    if not user.is_active:
        logger.warning("Inactive user attempted to access a protected endpoint")
        raise _credentials_exception("Inactive user")

    await db.execute(
        text("SELECT set_config('app.current_user_id', :user_id, true)"),
        {"user_id": str(user.id)},
    )
    
    return user
