from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.auth.dependencies import auth_dependency


class FakeTokenService:
    def decode_token(self, token: str) -> dict[str, str]:
        return {"sub": "1", "type": token}


class ValidTokenService:
    def decode_token(self, token: str) -> dict[str, str]:
        assert token == "access"
        return {"sub": "7", "type": "access"}


class FakeUserRepository:
    def __init__(self, db) -> None:
        self.db = db

    async def get_user_by_id(self, user_id: int):
        assert user_id == 7
        return SimpleNamespace(id=7, is_active=True)


class FakeDb:
    def __init__(self) -> None:
        self.executed = []

    async def execute(self, statement, params=None):
        self.executed.append((str(statement), params))


async def test_get_current_user_rejects_refresh_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_dependency, "TokenService", FakeTokenService)

    with pytest.raises(HTTPException) as exc_info:
        await auth_dependency.get_current_user(token="refresh", db=object())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token type"
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


async def test_get_current_user_sets_current_user_id_for_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_dependency, "TokenService", ValidTokenService)
    monkeypatch.setattr(auth_dependency, "UserRepository", FakeUserRepository)
    db = FakeDb()

    user = await auth_dependency.get_current_user(token="access", db=db)

    assert user.id == 7
    assert db.executed == [
        (
            "SELECT set_config('app.current_user_id', :user_id, true)",
            {"user_id": "7"},
        )
    ]
