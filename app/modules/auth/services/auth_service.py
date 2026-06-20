"""Servicios de autenticación.

Este módulo define `AuthService`, encargado de autenticar usuarios y emitir
tokens de acceso/refresh a partir de credenciales válidas.
"""

import logging
from datetime import UTC, datetime, timedelta

from app.core.config import config
from app.modules.auth.models.refresh_token_model import RefreshToken
from app.modules.auth.repositories.account_activation_token_repository import (
    AccountActivationTokenRepository,
)
from app.modules.auth.repositories.refresh_token_repository import (
    RefreshTokenRepository,
)
from app.modules.auth.schemas.token_schema import TokenResponse
from app.modules.auth.repositories.user_repository import UserRepository
from app.modules.auth.services.password_service import PasswordService
from app.modules.auth.services.token_service import TokenService


logger = logging.getLogger(__name__)


class TemporaryPasswordChangeRequiredError(Exception):
    """Indica que la credencial temporal debe reemplazarse antes de emitir sesión."""


class AccountActivationError(Exception):
    """Indica que un enlace de activacion no es valido o no puede usarse."""


class AuthService:
    """Orquesta el flujo de autenticación y emisión de tokens.

    El servicio delega responsabilidades en:

    - `UserRepository` para la obtención del usuario.
    - `PasswordService` para la verificación de contraseña.
    - `TokenService` para la creación de tokens.

    Attributes:
        password_service: Servicio de hashing/verificación de contraseñas.
        token_service: Servicio de creación de tokens.
        user_repository: Repositorio de acceso a usuarios.
    """

    def __init__(
        self,
        password_service: PasswordService,
        token_service: TokenService,
        user_repository: UserRepository,
        refresh_token_repository: RefreshTokenRepository,
        activation_token_repository: AccountActivationTokenRepository | None = None,
    ) -> None:
        """Inicializa el servicio con sus dependencias.

        Args:
            password_service: Servicio para verificar credenciales.
            token_service: Servicio para generar tokens.
            user_repository: Repositorio para consultar usuarios.
            refresh_token_repository: Repositorio para persistir refresh tokens.
        """

        self.password_service = password_service
        self.token_service = token_service
        self.user_repository = user_repository
        self.refresh_token_repository = refresh_token_repository
        self.activation_token_repository = activation_token_repository

    async def authenticate_user(self, email: str, password: str):
        """Autentica un usuario mediante correo y contraseña.

        Args:
            email: Correo electrónico del usuario.
            password: Contraseña en texto plano.

        Returns:
            La entidad de usuario si las credenciales son válidas; `None` en
            caso contrario.
        """

        user = await self.user_repository.get_user_by_email(email)

        if not user:
            logger.warning("Login attempt failed: user not found")
            return None

        is_valid_password = self.password_service.verify_password(
            password, user.password_hash
        )

        if not is_valid_password:
            logger.warning("Login attempt failed: invalid credentials")
            return None

        return user

    async def create_session_for_user(self, user) -> TokenResponse:
        """Emite tokens internos y persiste el refresh token revocable."""

        roles = [user_role.role.name for user_role in user.roles]
        subject = str(user.id)
        refresh_jti = self.token_service.generate_token_jti()

        access_token = self.token_service.create_access_token(
            subject=subject,
            email=user.email,
            roles=roles,
        )
        refresh_token = self.token_service.create_refresh_token(
            subject=subject,
            jti=refresh_jti,
        )

        expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(
            days=config.REFRESH_TOKEN_EXPIRE_DAYS
        )
        await self.refresh_token_repository.create_refresh_token(
            RefreshToken(
                user_id=user.id,
                jti=refresh_jti,
                token_hash=self.token_service.hash_token(refresh_token),
                expires_at=expires_at,
            )
        )

        return TokenResponse(access_token=access_token, refresh_token=refresh_token)

    async def refresh_session(self, refresh_token: str) -> TokenResponse:
        """Rota un refresh token persistido y emite una sesion nueva."""

        try:
            refresh_payload = self.token_service.decode_token(refresh_token)
        except ValueError:
            raise ValueError("Invalid or expired refresh token")

        if refresh_payload.get("type") != "refresh":
            raise ValueError("Invalid token type")

        refresh_sub = refresh_payload.get("sub")
        refresh_jti = refresh_payload.get("jti")

        try:
            user_id = int(refresh_sub)
        except (TypeError, ValueError):
            raise ValueError("Invalid token payload")

        if not isinstance(refresh_jti, str) or not refresh_jti:
            raise ValueError("Invalid token payload")

        persisted_refresh_token = (
            await self.refresh_token_repository.get_refresh_token_by_jti(refresh_jti)
        )

        if persisted_refresh_token is None:
            raise ValueError("Invalid refresh token")

        if persisted_refresh_token.user_id != user_id:
            raise ValueError("Invalid refresh token")

        if not self.refresh_token_repository.is_refresh_token_valid(
            persisted_refresh_token
        ):
            raise ValueError("Invalid refresh token")

        if not self.token_service.verify_token_hash(
            refresh_token,
            persisted_refresh_token.token_hash,
        ):
            raise ValueError("Invalid refresh token")

        user = await self.user_repository.get_user_by_id(user_id)

        if not user or not user.is_active:
            raise ValueError("Invalid refresh token")

        await self.refresh_token_repository.revoke_refresh_token(
            persisted_refresh_token
        )

        return await self.create_session_for_user(user)

    async def logout_session(self, current_user, refresh_token: str | None) -> None:
        """Revoca el refresh token de la sesion actual si fue enviado."""

        if refresh_token is None:
            return

        try:
            refresh_payload = self.token_service.decode_token(refresh_token)
        except ValueError:
            raise ValueError("Invalid refresh token")

        if refresh_payload.get("type") != "refresh":
            raise ValueError("Invalid token type")

        refresh_sub = refresh_payload.get("sub")
        refresh_jti = refresh_payload.get("jti")

        if refresh_sub is None or str(refresh_sub) != str(current_user.id):
            raise ValueError("Refresh token does not match current user")

        if not isinstance(refresh_jti, str) or not refresh_jti:
            raise ValueError("Invalid token payload")

        persisted_refresh_token = (
            await self.refresh_token_repository.get_refresh_token_by_jti(refresh_jti)
        )

        if persisted_refresh_token is None:
            raise ValueError("Invalid refresh token")

        if persisted_refresh_token.user_id != current_user.id:
            raise ValueError("Refresh token does not match current user")

        await self.refresh_token_repository.revoke_refresh_token(
            persisted_refresh_token
        )

    async def login(self, email: str, password: str) -> TokenResponse:
        """Inicia sesión y retorna tokens si las credenciales son válidas.

        Este método valida las credenciales y, si son correctas, genera un
        access token y un refresh token.

        Args:
            email: Correo electrónico del usuario.
            password: Contraseña en texto plano.

        Returns:
            `TokenResponse` con `access_token`, `refresh_token` y `token_type`.

        Raises:
            ValueError: Si las credenciales son inválidas.
        """

        user = await self.authenticate_user(email, password)

        if not user:
            raise ValueError("Invalid credentials")

        if user.must_change_password:
            raise TemporaryPasswordChangeRequiredError

        logger.info("User authenticated successfully")

        return await self.create_session_for_user(user)

    async def complete_temporary_password_change(
        self,
        *,
        email: str,
        temporary_password: str,
        new_password: str,
    ) -> None:
        """Reemplaza una credencial temporal valida por una contraseña definitiva."""

        user = await self.authenticate_user(email, temporary_password)

        if not user:
            raise ValueError("Invalid credentials")
        if not user.must_change_password:
            raise ValueError("Temporary password change is not required")

        user.password_hash = self.password_service.hash_password(new_password)
        user.must_change_password = False
        user.is_verified = True
        await self.user_repository.update_user(user)

        logger.info("Temporary password changed", extra={"user_id": user.id})

    async def activate_account(
        self,
        *,
        token: str,
        new_password: str,
    ) -> None:
        """Activa una cuenta usando un token de un solo uso y define contraseña."""

        if self.activation_token_repository is None:
            raise AccountActivationError("Account activation is not configured")

        token_hash = self.token_service.hash_token(token)
        activation_token = (
            await self.activation_token_repository.get_token_by_hash(token_hash)
        )

        if activation_token is None:
            raise AccountActivationError("Invalid or expired activation token")

        if not self.activation_token_repository.is_token_valid(activation_token):
            raise AccountActivationError("Invalid or expired activation token")

        user = activation_token.user

        if user is None or not user.is_active:
            raise AccountActivationError("Invalid or expired activation token")

        user.password_hash = self.password_service.hash_password(new_password)
        user.must_change_password = False
        user.is_verified = True

        await self.activation_token_repository.consume_token_for_user(
            activation_token,
            user,
        )

        logger.info("Account activated", extra={"user_id": user.id})
