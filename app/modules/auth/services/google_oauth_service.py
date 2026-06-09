"""Servicio para autenticacion con Google OAuth."""

import hashlib
import logging
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient

from app.core.config import Config, config
from app.modules.auth.models.user_model import User
from app.modules.auth.models.user_role_model import UserRole
from app.modules.auth.repositories.refresh_token_repository import RefreshTokenRepository
from app.modules.auth.repositories.role_repository import RoleRepository
from app.modules.auth.repositories.user_repository import UserRepository
from app.modules.auth.repositories.user_role_repository import UserRoleRepository
from app.modules.auth.schemas.token_schema import TokenResponse
from app.modules.auth.services.auth_service import AuthService
from app.modules.auth.services.password_service import PasswordService
from app.modules.auth.services.token_service import TokenService


logger = logging.getLogger(__name__)


class GoogleOAuthError(ValueError):
    """Error controlado del flujo OAuth expuesto como codigo al frontend."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class GoogleOAuthService:
    """Orquesta login OAuth con Google y emision del JWT de la aplicacion."""

    scopes = ("openid", "email", "profile")

    def __init__(
        self,
        token_service: TokenService,
        user_repository: UserRepository | None = None,
        refresh_token_repository: RefreshTokenRepository | None = None,
        role_repository: RoleRepository | None = None,
        user_role_repository: UserRoleRepository | None = None,
        password_service: PasswordService | None = None,
        settings: Config = config,
    ) -> None:
        self.token_service = token_service
        self.user_repository = user_repository
        self.refresh_token_repository = refresh_token_repository
        self.role_repository = role_repository
        self.user_role_repository = user_role_repository
        self.password_service = password_service
        self.settings = settings

    def build_authorization_url(self, state_token: str | None = None) -> str:
        """Construye la URL a la que el navegador debe redirigir."""

        self._validate_configuration()
        state = state_token or self.token_service.create_oauth_state_token()

        params = {
            "client_id": self.settings.GOOGLE_CLIENT_ID,
            "redirect_uri": self.settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state,
        }

        return (
            f"{self.settings.GOOGLE_AUTH_URI}"
            f"?{urlencode(params)}"
        )

    async def authenticate_callback(
        self,
        code: str | None,
        state: str | None,
    ) -> TokenResponse:
        """Valida el callback de Google y retorna tokens de la aplicacion."""

        if not code or not state:
            raise GoogleOAuthError(
                "invalid_callback",
                "Google OAuth callback missing code or state",
            )

        self._validate_state(state)

        token_payload = await self.exchange_authorization_code(code)
        id_token = token_payload.get("id_token")

        if not isinstance(id_token, str) or not id_token:
            raise GoogleOAuthError(
                "invalid_callback",
                "Google OAuth response did not include an id_token",
            )

        claims = self.verify_id_token(id_token)
        email = str(claims.get("email", "")).lower()

        if not email or not self._email_verified(claims):
            raise GoogleOAuthError(
                "invalid_callback",
                "Google OAuth identity is missing a verified email",
            )

        if not self._is_allowed_domain(email):
            raise GoogleOAuthError(
                "unauthorized_domain",
                "Google account domain is not allowed",
            )

        if self.user_repository is None:
            raise GoogleOAuthError(
                "server_unavailable",
                "User repository is not available",
            )

        user = await self._get_or_create_user(email=email, claims=claims)

        if user is None or not user.is_active:
            raise GoogleOAuthError(
                "user_not_found",
                "Google account is not linked to an active local user",
            )

        if self.refresh_token_repository is None:
            raise GoogleOAuthError(
                "server_unavailable",
                "Refresh token repository is not available",
            )

        auth_service = AuthService(
            user_repository=self.user_repository,
            refresh_token_repository=self.refresh_token_repository,
            password_service=self.password_service or PasswordService(),
            token_service=self.token_service,
        )
        token_response = await auth_service.create_session_for_user(user)

        logger.info(
            "Google OAuth login completed",
            extra={"user_id": user.id},
        )

        return token_response

    async def exchange_authorization_code(self, code: str) -> dict[str, Any]:
        """Intercambia el codigo OAuth por tokens de Google."""

        self._validate_configuration()

        payload = {
            "code": code,
            "client_id": self.settings.GOOGLE_CLIENT_ID,
            "client_secret": self.settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": self.settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.settings.GOOGLE_TOKEN_URI,
                    data=payload,
                )
        except httpx.RequestError as exc:
            logger.warning("Google OAuth token exchange failed: request error")
            raise GoogleOAuthError(
                "server_unavailable",
                "Google OAuth token endpoint is unavailable",
            ) from exc

        if response.status_code >= 400:
            logger.warning(
                "Google OAuth token exchange rejected",
                extra={"status_code": response.status_code},
            )
            raise GoogleOAuthError(
                "invalid_callback",
                "Google OAuth token exchange was rejected",
            )

        try:
            token_payload = response.json()
        except ValueError as exc:
            raise GoogleOAuthError(
                "invalid_callback",
                "Google OAuth token endpoint returned invalid JSON",
            ) from exc

        if not isinstance(token_payload, dict):
            raise GoogleOAuthError(
                "invalid_callback",
                "Google OAuth token endpoint returned an invalid payload",
            )

        return token_payload

    def verify_id_token(self, id_token: str) -> dict[str, Any]:
        """Verifica firma, audiencia, expiracion e issuer del id_token."""

        client_id = self.settings.GOOGLE_CLIENT_ID

        try:
            jwks_client = PyJWKClient(self.settings.GOOGLE_JWKS_URI)
            signing_key = jwks_client.get_signing_key_from_jwt(id_token)
            claims = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256"],
                audience=client_id,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise GoogleOAuthError(
                "invalid_callback",
                "Google OAuth id_token is invalid",
            ) from exc

        if claims.get("iss") not in {
            "accounts.google.com",
            "https://accounts.google.com",
        }:
            raise GoogleOAuthError(
                "invalid_callback",
                "Google OAuth id_token issuer is invalid",
            )

        return claims

    def _validate_state(self, state: str) -> None:
        try:
            self.token_service.decode_oauth_state_token(state)
        except ValueError as exc:
            raise GoogleOAuthError(
                "invalid_callback",
                "Google OAuth state is invalid",
            ) from exc

    async def _get_or_create_user(
        self,
        email: str,
        claims: dict[str, Any],
    ) -> User | None:
        if self.user_repository is None:
            raise GoogleOAuthError(
                "server_unavailable",
                "User repository is not available",
            )

        user = await self.user_repository.get_user_by_email(email)

        if user is not None:
            return user

        if (
            self.role_repository is None
            or self.user_role_repository is None
            or self.password_service is None
        ):
            raise GoogleOAuthError(
                "server_unavailable",
                "Google OAuth user provisioning is not configured",
            )

        student_role = await self.role_repository.get_role_by_name("Estudiante")

        if student_role is None:
            raise GoogleOAuthError(
                "server_unavailable",
                "Student role is not available",
            )

        first_name, last_name = self._profile_names(email=email, claims=claims)
        user = User(
            email=email,
            password_hash=self.password_service.hash_password(
                secrets.token_urlsafe(32)
            ),
            first_name=first_name,
            last_name=last_name,
            rut=self._synthetic_rut(claims),
            is_active=True,
            is_verified=True,
        )

        user = await self.user_repository.create_user(user)
        await self.user_role_repository.assign_role(
            UserRole(user_id=user.id, role_id=student_role.id)
        )

        return await self.user_repository.get_user_by_email(email)

    def _validate_configuration(self) -> None:
        if (
            not self.settings.GOOGLE_CLIENT_ID
            or not self.settings.GOOGLE_CLIENT_SECRET
            or not self.settings.GOOGLE_REDIRECT_URI
            or not self.settings.GOOGLE_FRONTEND_SUCCESS_URL
            or not self.settings.GOOGLE_FRONTEND_ERROR_URL
            or not self.settings.GOOGLE_ALLOWED_DOMAIN_LIST
        ):
            raise GoogleOAuthError(
                "server_unavailable",
                "Google OAuth client is not configured",
            )

    def _is_allowed_domain(self, email: str) -> bool:
        if "@" not in email:
            return False

        allowed_domains = self.settings.GOOGLE_ALLOWED_DOMAIN_LIST

        if not allowed_domains:
            return True

        domain = email.rsplit("@", 1)[1].lower()
        return domain in allowed_domains

    def _email_verified(self, claims: dict[str, Any]) -> bool:
        value = claims.get("email_verified")

        if isinstance(value, bool):
            return value

        return str(value).lower() == "true"

    def _profile_names(
        self,
        email: str,
        claims: dict[str, Any],
    ) -> tuple[str, str]:
        given_name = str(claims.get("given_name") or "").strip()
        family_name = str(claims.get("family_name") or "").strip()

        if given_name:
            return given_name, family_name or "Google"

        full_name = str(claims.get("name") or "").strip()

        if full_name:
            parts = full_name.split(maxsplit=1)
            return parts[0], parts[1] if len(parts) > 1 else "Google"

        local_part = email.split("@", 1)[0].replace(".", " ").strip()
        return local_part or "Usuario", "Google"

    def _synthetic_rut(self, claims: dict[str, Any]) -> str:
        google_sub = str(claims.get("sub") or "").strip()

        if not google_sub:
            raise GoogleOAuthError(
                "invalid_callback",
                "Google OAuth id_token is missing subject",
            )

        digest = hashlib.sha256(google_sub.encode("utf-8")).hexdigest()[:32]
        return f"google:{digest}"
