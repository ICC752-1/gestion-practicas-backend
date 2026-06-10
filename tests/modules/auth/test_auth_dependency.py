import pytest
from fastapi import HTTPException

from app.modules.auth.dependencies import auth_dependency


class FakeTokenService:
    def decode_token(self, token: str) -> dict[str, str]:
        return {"sub": "1", "type": token}


async def test_get_current_user_rejects_refresh_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_dependency, "TokenService", FakeTokenService)

    with pytest.raises(HTTPException) as exc_info:
        await auth_dependency.get_current_user(token="refresh", db=object())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token type"
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}
