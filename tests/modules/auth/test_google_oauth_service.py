from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from app.core.config import Config
from app.modules.auth.schemas.token_schema import TokenResponse
from app.modules.auth.services.google_oauth_service import (
    GoogleOAuthError,
    GoogleOAuthService,
)


class FakeTokenService:
    def __init__(self, valid_state: str = "state-token") -> None:
        self.valid_state = valid_state
        self.access_payload = None
        self.refresh_subject = None

    def create_oauth_state_token(self) -> str:
        return self.valid_state

    def decode_oauth_state_token(self, token: str):
        if token != self.valid_state:
            raise ValueError("invalid state")

        return {"typ": "oauth_state"}

    def create_access_token(self, subject: str, email: str, roles: list[str]) -> str:
        self.access_payload = {
            "subject": subject,
            "email": email,
            "roles": roles,
        }
        return "access-token"

    def create_refresh_token(self, subject: str) -> str:
        self.refresh_subject = subject
        return "refresh-token"


class FakeUserRepository:
    def __init__(self, user=None) -> None:
        self.user = user
        self.requested_email = None
        self.created_user = None

    async def get_user_by_email(self, email: str):
        self.requested_email = email
        return self.user

    async def create_user(self, user):
        self.created_user = user
        self.user = SimpleNamespace(
            id=3,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            password_hash=user.password_hash,
            rut=user.rut,
            is_active=user.is_active,
            is_verified=user.is_verified,
            roles=[],
        )
        return self.user


class FakeRoleRepository:
    def __init__(self, role=None) -> None:
        self.role = role or SimpleNamespace(id=1, name="Estudiante")
        self.requested_name = None

    async def get_role_by_name(self, role_name: str):
        self.requested_name = role_name
        return self.role


class FakeUserRoleRepository:
    def __init__(self, user_repository: FakeUserRepository) -> None:
        self.user_repository = user_repository
        self.assigned_role = None

    async def assign_role(self, user_role):
        self.assigned_role = user_role

        if self.user_repository.user is not None:
            self.user_repository.user.roles = [
                SimpleNamespace(role=SimpleNamespace(name="Estudiante"))
            ]

        return user_role


class FakePasswordService:
    def __init__(self) -> None:
        self.plain_password = None

    def hash_password(self, password: str) -> str:
        self.plain_password = password
        return "hashed-google-password"


def _settings(
    allowed_domains: str = "ufromail.cl,ufrontera.cl",
) -> Config:
    return Config(
        GOOGLE_CLIENT_ID="client-id",
        GOOGLE_CLIENT_SECRET="client-secret",
        GOOGLE_AUTH_URI="https://accounts.example/auth",
        GOOGLE_TOKEN_URI="https://accounts.example/token",
        GOOGLE_REDIRECT_URI="http://localhost:8000/auth/google/callback",
        GOOGLE_FRONTEND_SUCCESS_URL="http://localhost:5173/auth/callback",
        GOOGLE_FRONTEND_ERROR_URL="http://localhost:5173/auth/callback",
        GOOGLE_ALLOWED_DOMAINS=allowed_domains,
        _env_file=None,
    )


def _user(
    email: str = "claudio.navarro@ufrontera.cl",
    is_active: bool = True,
):
    return SimpleNamespace(
        id=2,
        email=email,
        is_active=is_active,
        roles=[
            SimpleNamespace(role=SimpleNamespace(name="Director de carrera")),
        ],
    )


def test_build_authorization_url_contains_google_parameters() -> None:
    token_service = FakeTokenService()
    service = GoogleOAuthService(
        token_service=token_service,
        settings=_settings(),
    )

    url = service.build_authorization_url()
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    assert parsed.geturl().startswith("https://accounts.example/auth?")
    assert params["client_id"] == ["client-id"]
    assert params["redirect_uri"] == [
        "http://localhost:8000/auth/google/callback"
    ]
    assert params["response_type"] == ["code"]
    assert params["scope"] == ["openid email profile"]
    assert params["state"] == ["state-token"]


async def test_authenticate_callback_issues_app_tokens_for_existing_user() -> None:
    token_service = FakeTokenService()
    repository = FakeUserRepository(user=_user())
    service = GoogleOAuthService(
        token_service=token_service,
        user_repository=repository,
        settings=_settings(),
    )

    async def exchange_authorization_code(code: str):
        assert code == "google-code"
        return {"id_token": "id-token"}

    service.exchange_authorization_code = exchange_authorization_code
    service.verify_id_token = lambda id_token: {
        "email": "claudio.navarro@ufrontera.cl",
        "email_verified": True,
        "sub": "google-sub-existing-user",
    }

    response = await service.authenticate_callback(
        code="google-code",
        state="state-token",
    )

    assert isinstance(response, TokenResponse)
    assert response.access_token == "access-token"
    assert response.refresh_token == "refresh-token"
    assert repository.requested_email == "claudio.navarro@ufrontera.cl"
    assert token_service.access_payload == {
        "subject": "2",
        "email": "claudio.navarro@ufrontera.cl",
        "roles": ["Director de carrera"],
    }
    assert token_service.refresh_subject == "2"


async def test_authenticate_callback_rejects_missing_callback_params() -> None:
    service = GoogleOAuthService(
        token_service=FakeTokenService(),
        user_repository=FakeUserRepository(user=_user()),
        settings=_settings(),
    )

    with pytest.raises(GoogleOAuthError) as exc_info:
        await service.authenticate_callback(code=None, state="state-token")

    assert exc_info.value.code == "invalid_callback"


async def test_authenticate_callback_rejects_invalid_state() -> None:
    service = GoogleOAuthService(
        token_service=FakeTokenService(),
        user_repository=FakeUserRepository(user=_user()),
        settings=_settings(),
    )

    with pytest.raises(GoogleOAuthError) as exc_info:
        await service.authenticate_callback(code="google-code", state="bad-state")

    assert exc_info.value.code == "invalid_callback"


async def test_authenticate_callback_rejects_unauthorized_domain() -> None:
    service = GoogleOAuthService(
        token_service=FakeTokenService(),
        user_repository=FakeUserRepository(user=_user(email="person@gmail.com")),
        settings=_settings(),
    )

    async def exchange_authorization_code(code: str):
        return {"id_token": "id-token"}

    service.exchange_authorization_code = exchange_authorization_code
    service.verify_id_token = lambda id_token: {
        "email": "person@gmail.com",
        "email_verified": True,
    }

    with pytest.raises(GoogleOAuthError) as exc_info:
        await service.authenticate_callback(
            code="google-code",
            state="state-token",
        )

    assert exc_info.value.code == "unauthorized_domain"


async def test_authenticate_callback_creates_student_for_allowed_domain() -> None:
    token_service = FakeTokenService()
    repository = FakeUserRepository(user=None)
    role_repository = FakeRoleRepository()
    user_role_repository = FakeUserRoleRepository(user_repository=repository)
    password_service = FakePasswordService()
    service = GoogleOAuthService(
        token_service=token_service,
        user_repository=repository,
        role_repository=role_repository,
        user_role_repository=user_role_repository,
        password_service=password_service,
        settings=_settings(),
    )

    async def exchange_authorization_code(code: str):
        return {"id_token": "id-token"}

    service.exchange_authorization_code = exchange_authorization_code
    service.verify_id_token = lambda id_token: {
        "email": "nuevo.estudiante@ufromail.cl",
        "email_verified": True,
        "given_name": "Nuevo",
        "family_name": "Estudiante",
        "sub": "google-sub-new-user",
    }

    response = await service.authenticate_callback(
        code="google-code",
        state="state-token",
    )

    assert response.access_token == "access-token"
    assert repository.created_user.email == "nuevo.estudiante@ufromail.cl"
    assert repository.created_user.first_name == "Nuevo"
    assert repository.created_user.last_name == "Estudiante"
    assert repository.created_user.password_hash == "hashed-google-password"
    assert repository.created_user.rut.startswith("google:")
    assert repository.created_user.is_active is True
    assert repository.created_user.is_verified is True
    assert role_repository.requested_name == "Estudiante"
    assert user_role_repository.assigned_role.user_id == 3
    assert user_role_repository.assigned_role.role_id == 1
    assert token_service.access_payload == {
        "subject": "3",
        "email": "nuevo.estudiante@ufromail.cl",
        "roles": ["Estudiante"],
    }


async def test_exchange_authorization_code_rejects_invalid_code(monkeypatch) -> None:
    class FakeResponse:
        status_code = 400

        def json(self):
            return {"error": "invalid_grant"}

    class FakeAsyncClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url: str, data: dict[str, str]):
            return FakeResponse()

    monkeypatch.setattr(
        "app.modules.auth.services.google_oauth_service.httpx.AsyncClient",
        FakeAsyncClient,
    )
    service = GoogleOAuthService(
        token_service=FakeTokenService(),
        settings=_settings(),
    )

    with pytest.raises(GoogleOAuthError) as exc_info:
        await service.exchange_authorization_code("invalid-code")

    assert exc_info.value.code == "invalid_callback"
