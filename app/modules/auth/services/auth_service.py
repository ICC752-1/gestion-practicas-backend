"""Servicios de autenticación.

Este módulo define `AuthService`, encargado de autenticar usuarios y emitir
tokens de acceso/refresh a partir de credenciales válidas.
"""

import logging

from app.modules.auth.schemas.token_schema import TokenResponse
from app.modules.auth.repositories.user_repository import UserRepository
from app.modules.auth.services.password_service import PasswordService
from app.modules.auth.services.token_service import TokenService


logger = logging.getLogger(__name__)


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

    def __init__(self, password_service: PasswordService, token_service: TokenService, user_repository: UserRepository) -> None:
        """Inicializa el servicio con sus dependencias.

        Args:
            password_service: Servicio para verificar credenciales.
            token_service: Servicio para generar tokens.
            user_repository: Repositorio para consultar usuarios.
        """

        self.password_service = password_service
        self.token_service = token_service
        self.user_repository = user_repository
    
    async def authenticate_user(self, email:str, password:str):
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

        is_valid_password = self.password_service.verify_password(password, user.password_hash)

        if not is_valid_password:
            logger.warning("Login attempt failed: invalid credentials")
            return None

        return user

    async def login(self, email:str, password:str) -> TokenResponse:
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

        roles = [user_role.role.name for user_role in user.roles]

        access_token = self.token_service.create_access_token(subject=str(user.id), email=user.email, roles=roles)
        refresh_token = self.token_service.create_refresh_token(subject=str(user.id))

        logger.info("User authenticated successfully")

        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
