"""Controlador (router) de autenticación.

Este módulo define las rutas HTTP relacionadas con autenticación y obtención de
información del usuario autenticado.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.dependencies.auth_dependency import get_current_user
from app.core.database import get_db

from app.modules.auth.repositories.user_repository import UserRepository

from app.modules.auth.schemas.auth_schema import LoginRequest
from app.modules.auth.schemas.token_schema import TokenResponse
from app.modules.auth.schemas.user_schema import CurrentUserResponse

from app.modules.auth.models.user_model import User

from app.modules.auth.services.auth_service import AuthService
from app.modules.auth.services.password_service import PasswordService
from app.modules.auth.services.token_service import TokenService

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Inicia sesión y devuelve tokens de acceso y refresco.

    Valida las credenciales y, si son correctas, emite un `TokenResponse`.

    Args:
        credentials: Credenciales de inicio de sesión (email y password).
        db: Sesión asíncrona de base de datos inyectada por `get_db`.

    Returns:
        `TokenResponse` con `access_token`, `refresh_token` y `token_type`.

    Raises:
        HTTPException: Con código 401 si el email o la contraseña son inválidos.
    """

    user_repository = UserRepository(db)

    auth_service = AuthService(
        user_repository=user_repository,
        password_service=PasswordService(),
        token_service=TokenService()
    )

    try:
        return await auth_service.login(email=credentials.email, password=credentials.password)
    
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

@router.get("/me", response_model=CurrentUserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> CurrentUserResponse:
    """Devuelve información del usuario autenticado.

    Args:
        current_user: Usuario autenticado inyectado por `get_current_user`.

    Returns:
        `CurrentUserResponse` con datos del usuario y sus roles.
    """

    return CurrentUserResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        roles=[user_role.role.name for user_role in current_user.roles]
    )