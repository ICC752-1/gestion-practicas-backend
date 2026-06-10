from types import SimpleNamespace

import pytest

from app.modules.auth.schemas.token_schema import TokenResponse
from app.modules.auth.services.auth_service import AuthService


class FakeUserRepository:
    def __init__(self, user=None) -> None:
        self.user = user
        self.requested_email = None
        self.requested_user_id = None

    async def get_user_by_email(self, email: str):
        self.requested_email = email
        return self.user

    async def get_user_by_id(self, user_id: int):
        self.requested_user_id = user_id
        return self.user


class FakePasswordService:
    def __init__(self, is_valid: bool) -> None:
        self.is_valid = is_valid
        self.calls: list[tuple[str, str]] = []

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        self.calls.append((plain_password, hashed_password))
        return self.is_valid


class FakeTokenService:
    def __init__(self, decoded_payload=None, decode_error: bool = False) -> None:
        self.access_payload = None
        self.decode_error = decode_error
        self.decoded_payload = decoded_payload or {
            "sub": "1",
            "jti": "old-jti",
            "type": "refresh",
        }
        self.refresh_subject = None
        self.refresh_jti = None

    def create_access_token(self, subject: str, email: str, roles: list[str]) -> str:
        self.access_payload = {
            "subject": subject,
            "email": email,
            "roles": roles,
        }
        return "access-token"

    def generate_token_jti(self) -> str:
        return "refresh-jti"

    def create_refresh_token(self, subject: str, jti: str | None = None) -> str:
        self.refresh_subject = subject
        self.refresh_jti = jti
        return "refresh-token"

    def hash_token(self, token: str) -> str:
        return f"hashed-{token}"

    def verify_token_hash(self, token: str, token_hash: str) -> bool:
        return self.hash_token(token) == token_hash

    def decode_token(self, token: str):
        if self.decode_error:
            raise ValueError("Invalid token")

        return self.decoded_payload


class FakeRefreshTokenRepository:
    def __init__(self, stored_refresh_token=None) -> None:
        self.created_refresh_token = None
        self.created_refresh_tokens = []
        self.requested_jti = None
        self.revoked_refresh_token = None
        self.stored_refresh_token = stored_refresh_token

    async def create_refresh_token(self, refresh_token):
        self.created_refresh_token = refresh_token
        self.created_refresh_tokens.append(refresh_token)
        return refresh_token

    async def get_refresh_token_by_jti(self, jti: str):
        self.requested_jti = jti
        return self.stored_refresh_token

    async def revoke_refresh_token(self, refresh_token):
        self.revoked_refresh_token = refresh_token
        refresh_token.revoked_at = "revoked"
        return refresh_token

    def is_refresh_token_valid(self, refresh_token) -> bool:
        return getattr(refresh_token, "is_valid", True)


def _user(is_active: bool = True):
    return SimpleNamespace(
        id=1,
        email="user@example.com",
        is_active=is_active,
        password_hash="hashed",
        roles=[SimpleNamespace(role=SimpleNamespace(name="Estudiante"))],
    )


def _stored_refresh_token(
    user_id: int = 1,
    token_hash: str = "hashed-old-refresh-token",
    is_valid: bool = True,
):
    return SimpleNamespace(
        user_id=user_id,
        token_hash=token_hash,
        is_valid=is_valid,
        revoked_at=None,
    )


def _service(
    user=None,
    is_valid_password: bool = True,
    decoded_payload=None,
    decode_error: bool = False,
    stored_refresh_token=None,
):
    repository = FakeUserRepository(user=user)
    password_service = FakePasswordService(is_valid=is_valid_password)
    token_service = FakeTokenService(
        decoded_payload=decoded_payload,
        decode_error=decode_error,
    )
    refresh_token_repository = FakeRefreshTokenRepository(
        stored_refresh_token=stored_refresh_token
    )
    service = AuthService(
        password_service=password_service,
        token_service=token_service,
        user_repository=repository,
        refresh_token_repository=refresh_token_repository,
    )

    return service, repository, password_service, token_service, refresh_token_repository


async def test_authenticate_user_returns_user_with_valid_credentials() -> None:
    user = _user()
    service, repository, _, _, _ = _service(user=user)

    result = await service.authenticate_user("user@example.com", "secret")

    assert result is user
    assert repository.requested_email == "user@example.com"


async def test_authenticate_user_returns_none_when_user_missing() -> None:
    service, _, _, _, _ = _service(user=None)

    result = await service.authenticate_user("missing@example.com", "secret")

    assert result is None


async def test_authenticate_user_returns_none_for_invalid_password() -> None:
    user = _user()
    service, _, _, _, _ = _service(user=user, is_valid_password=False)

    result = await service.authenticate_user("user@example.com", "secret")

    assert result is None


async def test_login_returns_tokens_for_valid_credentials() -> None:
    user = _user()
    service, _, _, token_service, refresh_token_repository = _service(user=user)

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
    assert token_service.refresh_jti == "refresh-jti"

    persisted_refresh_token = refresh_token_repository.created_refresh_token
    assert persisted_refresh_token is not None
    assert persisted_refresh_token.user_id == 1
    assert persisted_refresh_token.jti == "refresh-jti"
    assert persisted_refresh_token.token_hash == "hashed-refresh-token"
    assert persisted_refresh_token.token_hash != response.refresh_token
    assert persisted_refresh_token.expires_at is not None


async def test_create_session_for_user_returns_tokens_and_persists_refresh_token() -> None:
    user = _user()
    service, _, _, token_service, refresh_token_repository = _service(user=user)

    response = await service.create_session_for_user(user)

    assert response.access_token == "access-token"
    assert response.refresh_token == "refresh-token"
    assert token_service.access_payload == {
        "subject": "1",
        "email": "user@example.com",
        "roles": ["Estudiante"],
    }
    assert token_service.refresh_subject == "1"
    assert token_service.refresh_jti == "refresh-jti"

    persisted_refresh_token = refresh_token_repository.created_refresh_token
    assert persisted_refresh_token is not None
    assert persisted_refresh_token.user_id == 1
    assert persisted_refresh_token.jti == "refresh-jti"
    assert persisted_refresh_token.token_hash == "hashed-refresh-token"


async def test_refresh_session_rotates_valid_refresh_token() -> None:
    user = _user()
    stored_refresh_token = _stored_refresh_token()
    service, user_repository, _, _, refresh_token_repository = _service(
        user=user,
        stored_refresh_token=stored_refresh_token,
    )

    response = await service.refresh_session("old-refresh-token")

    assert response.access_token == "access-token"
    assert response.refresh_token == "refresh-token"
    assert user_repository.requested_user_id == 1
    assert refresh_token_repository.requested_jti == "old-jti"
    assert refresh_token_repository.revoked_refresh_token is stored_refresh_token
    assert refresh_token_repository.created_refresh_token is not stored_refresh_token
    assert refresh_token_repository.created_refresh_token.jti == "refresh-jti"


@pytest.mark.parametrize(
    "decoded_payload",
    [
        {"sub": "1", "jti": "old-jti", "type": "access"},
        {"sub": "invalid", "jti": "old-jti", "type": "refresh"},
        {"sub": "1", "type": "refresh"},
        {"sub": "1", "jti": "", "type": "refresh"},
    ],
)
async def test_refresh_session_rejects_invalid_payload(decoded_payload) -> None:
    service, _, _, _, _ = _service(
        user=_user(),
        decoded_payload=decoded_payload,
        stored_refresh_token=_stored_refresh_token(),
    )

    with pytest.raises(ValueError):
        await service.refresh_session("old-refresh-token")


async def test_refresh_session_rejects_decode_errors() -> None:
    service, _, _, _, _ = _service(user=_user(), decode_error=True)

    with pytest.raises(ValueError, match="Invalid or expired refresh token"):
        await service.refresh_session("old-refresh-token")


@pytest.mark.parametrize(
    "stored_refresh_token",
    [
        None,
        _stored_refresh_token(user_id=2),
        _stored_refresh_token(is_valid=False),
        _stored_refresh_token(token_hash="different-hash"),
    ],
)
async def test_refresh_session_rejects_invalid_persisted_token(
    stored_refresh_token,
) -> None:
    service, _, _, _, _ = _service(
        user=_user(),
        stored_refresh_token=stored_refresh_token,
    )

    with pytest.raises(ValueError, match="Invalid refresh token"):
        await service.refresh_session("old-refresh-token")


async def test_refresh_session_rejects_missing_user() -> None:
    service, _, _, _, _ = _service(
        user=None,
        stored_refresh_token=_stored_refresh_token(),
    )

    with pytest.raises(ValueError, match="Invalid refresh token"):
        await service.refresh_session("old-refresh-token")


async def test_refresh_session_rejects_inactive_user() -> None:
    service, _, _, _, _ = _service(
        user=_user(is_active=False),
        stored_refresh_token=_stored_refresh_token(),
    )

    with pytest.raises(ValueError, match="Invalid refresh token"):
        await service.refresh_session("old-refresh-token")


async def test_logout_session_revokes_refresh_token() -> None:
    user = _user()
    stored_refresh_token = _stored_refresh_token()
    service, _, _, _, refresh_token_repository = _service(
        user=user,
        stored_refresh_token=stored_refresh_token,
    )

    await service.logout_session(user, "old-refresh-token")

    assert refresh_token_repository.requested_jti == "old-jti"
    assert refresh_token_repository.revoked_refresh_token is stored_refresh_token


async def test_logout_session_without_refresh_token_does_not_revoke() -> None:
    user = _user()
    service, _, _, _, refresh_token_repository = _service(
        user=user,
        stored_refresh_token=_stored_refresh_token(),
    )

    await service.logout_session(user, None)

    assert refresh_token_repository.requested_jti is None
    assert refresh_token_repository.revoked_refresh_token is None


async def test_logout_session_rejects_decode_errors() -> None:
    service, _, _, _, _ = _service(user=_user(), decode_error=True)

    with pytest.raises(ValueError, match="Invalid refresh token"):
        await service.logout_session(_user(), "old-refresh-token")


@pytest.mark.parametrize(
    ("decoded_payload", "error_match"),
    [
        ({"sub": "1", "jti": "old-jti", "type": "access"}, "Invalid token type"),
        ({"sub": "2", "jti": "old-jti", "type": "refresh"}, "does not match"),
        ({"sub": "1", "type": "refresh"}, "Invalid token payload"),
        ({"sub": "1", "jti": "", "type": "refresh"}, "Invalid token payload"),
    ],
)
async def test_logout_session_rejects_invalid_payload(
    decoded_payload,
    error_match: str,
) -> None:
    service, _, _, _, _ = _service(
        user=_user(),
        decoded_payload=decoded_payload,
        stored_refresh_token=_stored_refresh_token(),
    )

    with pytest.raises(ValueError, match=error_match):
        await service.logout_session(_user(), "old-refresh-token")


@pytest.mark.parametrize(
    ("stored_refresh_token", "error_match"),
    [
        (None, "Invalid refresh token"),
        (_stored_refresh_token(user_id=2), "does not match"),
    ],
)
async def test_logout_session_rejects_invalid_persisted_token(
    stored_refresh_token,
    error_match: str,
) -> None:
    service, _, _, _, _ = _service(
        user=_user(),
        stored_refresh_token=stored_refresh_token,
    )

    with pytest.raises(ValueError, match=error_match):
        await service.logout_session(_user(), "old-refresh-token")


async def test_login_raises_for_invalid_credentials() -> None:
    service, _, _, _, _ = _service(user=None, is_valid_password=False)

    with pytest.raises(ValueError, match="Invalid credentials"):
        await service.login("user@example.com", "secret")
