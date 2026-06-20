import pytest
from fastapi import HTTPException

from app.modules.auth.dependencies import auth_dependency


class FakeTokenService:
    decoded_payload = {"sub": "1", "type": "access"}
    decode_error = False

    def decode_token(self, token: str) -> dict[str, str]:
        if self.decode_error:
            raise ValueError("Token inválido")

        if token == "refresh":
            return {"sub": "1", "type": "refresh"}

        return self.decoded_payload


class FakeUserRepository:
    user = None
    requested_user_id = None

    def __init__(self, db) -> None:
        self.db = db

    async def get_user_by_id(self, user_id: int):
        self.__class__.requested_user_id = user_id
        return self.user


def _user(is_active: bool = True):
    return type(
        "FakeUser",
        (),
        {
            "id": 1,
            "email": "user@example.com",
            "is_active": is_active,
        },
    )()


@pytest.fixture(autouse=True)
def _reset_fakes(monkeypatch: pytest.MonkeyPatch):
    FakeTokenService.decoded_payload = {"sub": "1", "type": "access"}
    FakeTokenService.decode_error = False
    FakeUserRepository.user = _user()
    FakeUserRepository.requested_user_id = None
    monkeypatch.setattr(auth_dependency, "TokenService", FakeTokenService)
    monkeypatch.setattr(auth_dependency, "UserRepository", FakeUserRepository)


async def test_get_current_user_returns_active_user_from_access_token() -> None:
    result = await auth_dependency.get_current_user(token="access", db=object())

    assert result is FakeUserRepository.user
    assert FakeUserRepository.requested_user_id == 1


async def test_get_current_user_rejects_refresh_token(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await auth_dependency.get_current_user(token="refresh", db=object())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token type"
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


async def test_get_current_user_rejects_decode_errors() -> None:
    FakeTokenService.decode_error = True

    with pytest.raises(HTTPException) as exc_info:
        await auth_dependency.get_current_user(token="invalid", db=object())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token"


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "access"},
        {"sub": "invalid", "type": "access"},
    ],
)
async def test_get_current_user_rejects_invalid_subject(payload) -> None:
    FakeTokenService.decoded_payload = payload

    with pytest.raises(HTTPException) as exc_info:
        await auth_dependency.get_current_user(token="access", db=object())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token payload"


async def test_get_current_user_rejects_missing_user() -> None:
    FakeUserRepository.user = None

    with pytest.raises(HTTPException) as exc_info:
        await auth_dependency.get_current_user(token="access", db=object())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "User not found"


async def test_get_current_user_rejects_inactive_user() -> None:
    FakeUserRepository.user = _user(is_active=False)

    with pytest.raises(HTTPException) as exc_info:
        await auth_dependency.get_current_user(token="access", db=object())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Inactive user"
