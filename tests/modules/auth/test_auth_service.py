from types import SimpleNamespace

import pytest

from app.modules.auth.schemas.token_schema import TokenResponse
from app.modules.auth.services.auth_service import AuthService


class FakeUserRepository:
    def __init__(self, user=None) -> None:
        self.user = user
        self.requested_email = None

    async def get_user_by_email(self, email: str):
        self.requested_email = email
        return self.user


class FakePasswordService:
    def __init__(self, is_valid: bool) -> None:
        self.is_valid = is_valid
        self.calls: list[tuple[str, str]] = []

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        self.calls.append((plain_password, hashed_password))
        return self.is_valid


class FakeTokenService:
    def __init__(self) -> None:
        self.access_payload = None
        self.refresh_subject = None

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


def _user():
    return SimpleNamespace(
        id=1,
        email="user@example.com",
        password_hash="hashed",
        roles=[SimpleNamespace(role=SimpleNamespace(name="Estudiante"))],
    )


async def test_authenticate_user_returns_user_with_valid_credentials() -> None:
    user = _user()
    repository = FakeUserRepository(user=user)
    password_service = FakePasswordService(is_valid=True)
    token_service = FakeTokenService()
    service = AuthService(
        password_service=password_service,
        token_service=token_service,
        user_repository=repository,
    )

    result = await service.authenticate_user("user@example.com", "secret")

    assert result is user
    assert repository.requested_email == "user@example.com"


async def test_authenticate_user_returns_none_when_user_missing() -> None:
    repository = FakeUserRepository(user=None)
    password_service = FakePasswordService(is_valid=True)
    token_service = FakeTokenService()
    service = AuthService(
        password_service=password_service,
        token_service=token_service,
        user_repository=repository,
    )

    result = await service.authenticate_user("missing@example.com", "secret")

    assert result is None


async def test_authenticate_user_returns_none_for_invalid_password() -> None:
    user = _user()
    repository = FakeUserRepository(user=user)
    password_service = FakePasswordService(is_valid=False)
    token_service = FakeTokenService()
    service = AuthService(
        password_service=password_service,
        token_service=token_service,
        user_repository=repository,
    )

    result = await service.authenticate_user("user@example.com", "secret")

    assert result is None


async def test_login_returns_tokens_for_valid_credentials() -> None:
    user = _user()
    repository = FakeUserRepository(user=user)
    password_service = FakePasswordService(is_valid=True)
    token_service = FakeTokenService()
    service = AuthService(
        password_service=password_service,
        token_service=token_service,
        user_repository=repository,
    )

    response = await service.login("user@example.com", "secret")

    assert isinstance(response, TokenResponse)
    assert response.access_token == "access-token"
    assert response.refresh_token == "refresh-token"
    assert response.token_type == "bearer"
    assert token_service.access_payload == {
        "subject": "1",
        "email": "user@example.com",
        "roles": ["Estudiante"],
    }
    assert token_service.refresh_subject == "1"


async def test_login_raises_for_invalid_credentials() -> None:
    repository = FakeUserRepository(user=None)
    password_service = FakePasswordService(is_valid=False)
    token_service = FakeTokenService()
    service = AuthService(
        password_service=password_service,
        token_service=token_service,
        user_repository=repository,
    )

    with pytest.raises(ValueError, match="Invalid credentials"):
        await service.login("user@example.com", "secret")
