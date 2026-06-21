"""Controlador (router) de autenticación.

Este módulo define las rutas HTTP relacionadas con autenticación y obtención de
información del usuario autenticado.
"""

import logging
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import config
from app.modules.auth.dependencies.auth_dependency import get_current_user
from app.core.database.database import get_db

from app.modules.auth.repositories.refresh_token_repository import RefreshTokenRepository
from app.modules.auth.repositories.account_activation_token_repository import (
    AccountActivationTokenRepository,
)
from app.modules.auth.repositories.role_repository import RoleRepository
from app.modules.auth.repositories.user_repository import UserRepository
from app.modules.auth.repositories.user_role_repository import UserRoleRepository

from app.modules.auth.schemas.auth_schema import (
    ActivationAccountInfoResponse,
    ActivateAccountRequest,
    CompleteTemporaryPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
)
from app.modules.auth.schemas.token_schema import TokenResponse
from app.modules.auth.schemas.user_schema import CurrentUserResponse

from app.modules.auth.models.user_model import User

from app.modules.auth.services.auth_service import (
    AccountActivationError,
    AuthService,
    TemporaryPasswordChangeRequiredError,
)
from app.modules.auth.services.google_oauth_service import (
    GoogleOAuthError,
    GoogleOAuthService,
)
from app.modules.auth.services.password_service import PasswordService
from app.modules.auth.services.token_service import TokenService

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)


def _set_refresh_token_cookie(
    response: Response,
    refresh_token: str,
) -> None:
    response.set_cookie(
        config.REFRESH_TOKEN_COOKIE_NAME,
        refresh_token,
        httponly=True,
        max_age=config.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
        samesite="lax",
        secure=config.REFRESH_TOKEN_COOKIE_SECURE,
    )


def _clear_refresh_token_cookie(response: Response) -> None:
    response.delete_cookie(
        config.REFRESH_TOKEN_COOKIE_NAME,
        path="/",
    )


def _frontend_callback_url(params: dict[str, str], success: bool) -> str:
    base_url = (
        config.GOOGLE_FRONTEND_SUCCESS_URL
        if success
        else config.GOOGLE_FRONTEND_ERROR_URL
    )
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode(params)}"


def _oauth_error_redirect(
    error_code: str,
    clear_state_cookie: bool = False,
) -> RedirectResponse:
    response = RedirectResponse(
        _frontend_callback_url({"error": error_code}, success=False),
        status_code=status.HTTP_303_SEE_OTHER,
    )

    if clear_state_cookie:
        response.delete_cookie(config.GOOGLE_STATE_COOKIE_NAME, path="/")

    return response


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    response: Response,
) -> TokenResponse:
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
    refresh_token_repository = RefreshTokenRepository(db)

    auth_service = AuthService(
        user_repository=user_repository,
        refresh_token_repository=refresh_token_repository,
        password_service=PasswordService(),
        token_service=TokenService()
    )

    try:
        logger.info("Login request received")
        token_response = await auth_service.login(
            email=credentials.email,
            password=credentials.password,
        )
        _set_refresh_token_cookie(response, token_response.refresh_token)
        return token_response

    except TemporaryPasswordChangeRequiredError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="TEMPORARY_PASSWORD_CHANGE_REQUIRED",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/complete-temporary-password", status_code=status.HTTP_204_NO_CONTENT)
async def complete_temporary_password(
    payload: CompleteTemporaryPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Reemplaza una credencial temporal de un solo uso por contraseña definitiva."""

    user_repository = UserRepository(db)
    refresh_token_repository = RefreshTokenRepository(db)
    auth_service = AuthService(
        user_repository=user_repository,
        refresh_token_repository=refresh_token_repository,
        password_service=PasswordService(),
        token_service=TokenService(),
    )

    try:
        await auth_service.complete_temporary_password_change(
            email=payload.email,
            temporary_password=payload.temporary_password,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/activate-account", status_code=status.HTTP_204_NO_CONTENT)
async def activate_account(
    payload: ActivateAccountRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Activa una cuenta nueva mediante enlace de un solo uso."""

    auth_service = AuthService(
        user_repository=UserRepository(db),
        refresh_token_repository=RefreshTokenRepository(db),
        activation_token_repository=AccountActivationTokenRepository(db),
        password_service=PasswordService(),
        token_service=TokenService(),
    )

    try:
        await auth_service.activate_account(
            token=payload.token,
            new_password=payload.new_password,
            admission_year=payload.admission_year,
        )
    except AccountActivationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/activation-info", response_model=ActivationAccountInfoResponse)
async def get_activation_info(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: str = Query(min_length=32, max_length=512),
) -> ActivationAccountInfoResponse:
    """Devuelve datos mínimos para completar una activacion por enlace."""

    auth_service = AuthService(
        user_repository=UserRepository(db),
        refresh_token_repository=RefreshTokenRepository(db),
        activation_token_repository=AccountActivationTokenRepository(db),
        password_service=PasswordService(),
        token_service=TokenService(),
    )

    try:
        info = await auth_service.get_activation_account_info(token=token)
    except AccountActivationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return ActivationAccountInfoResponse(**info)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    db: Annotated[AsyncSession, Depends(get_db)],
    response: Response,
    refresh_token_cookie: Annotated[
        str | None,
        Cookie(alias=config.REFRESH_TOKEN_COOKIE_NAME),
    ] = None,
    payload: RefreshTokenRequest | None = None,
) -> TokenResponse:
    """Renueva tokens usando un refresh token valido.

    Args:
        payload: Solicitud con refresh token emitido previamente.
        db: Sesion asincrona de base de datos inyectada por `get_db`.

    Returns:
        `TokenResponse` con nuevos tokens de acceso y refresco.

    Raises:
        HTTPException: 401 si el refresh token es invalido, expiro, no es de
            tipo refresh o el usuario asociado no existe/esta inactivo.
    """

    user_repository = UserRepository(db)
    refresh_token_repository = RefreshTokenRepository(db)
    auth_service = AuthService(
        user_repository=user_repository,
        refresh_token_repository=refresh_token_repository,
        password_service=PasswordService(),
        token_service=TokenService(),
    )

    try:
        refresh_token_value = (
            payload.refresh_token if payload and payload.refresh_token else refresh_token_cookie
        )
        if refresh_token_value is None:
            raise ValueError("Refresh token is required")

        token_response = await auth_service.refresh_session(refresh_token_value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _set_refresh_token_cookie(response, token_response.refresh_token)
    logger.info("Refresh token completed")

    return token_response


@router.get("/google/login")
async def google_login() -> RedirectResponse:
    """Redirige el navegador al flujo OAuth de Google."""

    token_service = TokenService()
    state_token = token_service.create_oauth_state_token()
    google_oauth_service = GoogleOAuthService(token_service=token_service)

    try:
        authorization_url = google_oauth_service.build_authorization_url(
            state_token=state_token,
        )
    except GoogleOAuthError as exc:
        logger.warning("Google OAuth login could not start")
        return _oauth_error_redirect(exc.code)

    response = RedirectResponse(authorization_url)
    response.set_cookie(
        config.GOOGLE_STATE_COOKIE_NAME,
        state_token,
        httponly=True,
        max_age=config.GOOGLE_STATE_EXPIRE_MINUTES * 60,
        path="/",
        samesite="lax",
        secure=config.GOOGLE_COOKIE_SECURE,
    )

    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Procesa el callback de Google y redirige al callback del frontend."""

    if error:
        logger.warning(
            "Google OAuth callback returned an error",
            extra={"oauth_error": error},
        )
        return _oauth_error_redirect(
            "invalid_callback",
            clear_state_cookie=True,
        )

    state_cookie = request.cookies.get(config.GOOGLE_STATE_COOKIE_NAME)

    if not state or state != state_cookie:
        logger.warning("Google OAuth callback state cookie mismatch")
        return _oauth_error_redirect(
            "invalid_callback",
            clear_state_cookie=True,
        )

    user_repository = UserRepository(db)
    google_oauth_service = GoogleOAuthService(
        user_repository=user_repository,
        role_repository=RoleRepository(db),
        user_role_repository=UserRoleRepository(db),
        password_service=PasswordService(),
        token_service=TokenService(),
        refresh_token_repository=RefreshTokenRepository(db),
    )

    try:
        token_response = await google_oauth_service.authenticate_callback(
            code=code,
            state=state,
        )
    except GoogleOAuthError as exc:
        logger.warning(
            "Google OAuth callback failed",
            extra={"oauth_error": exc.code},
        )
        return _oauth_error_redirect(exc.code, clear_state_cookie=True)

    response = RedirectResponse(
        _frontend_callback_url(
            {"token": token_response.access_token},
            success=True,
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    response.delete_cookie(config.GOOGLE_STATE_COOKIE_NAME, path="/")
    _set_refresh_token_cookie(response, token_response.refresh_token)
    return response


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> CurrentUserResponse:
    """Devuelve información del usuario autenticado.

    Args:
        current_user: Usuario autenticado inyectado por `get_current_user`.

    Returns:
        `CurrentUserResponse` con datos del usuario y sus roles.
    """

    logger.info(
        "Get current user completed",
        extra={"user_id": current_user.id},
    )

    return CurrentUserResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        roles=[user_role.role.name for user_role in current_user.roles]
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    payload: LogoutRequest | None = None,
    refresh_token_cookie: Annotated[
        str | None,
        Cookie(alias=config.REFRESH_TOKEN_COOKIE_NAME),
    ] = None,
) -> Response:
    """Cierra sesión (logout) para el dispositivo actual.

    Si el frontend envía un `refresh_token`, se valida que pertenezca al usuario
    autenticado y se revoca en base de datos.

    Args:
        current_user: Usuario autenticado (access token válido).
        db: Sesión asíncrona de base de datos inyectada por `get_db`.
        payload: Opcional. Incluye `refresh_token` para validación.

    Returns:
        Respuesta vacía con código 204.
    """

    user_repository = UserRepository(db)
    refresh_token_repository = RefreshTokenRepository(db)
    auth_service = AuthService(
        user_repository=user_repository,
        refresh_token_repository=refresh_token_repository,
        password_service=PasswordService(),
        token_service=TokenService(),
    )

    try:
        await auth_service.logout_session(
            current_user=current_user,
            refresh_token=(
                payload.refresh_token
                if payload and payload.refresh_token
                else refresh_token_cookie
            ),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    logger.info("Logout request received", extra={"user_id": current_user.id})
    logger.info("Logout completed", extra={"user_id": current_user.id})
    final_response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_refresh_token_cookie(final_response)
    return final_response
