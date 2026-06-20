from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.auth.controllers import auth_controller
from app.modules.auth.schemas.auth_schema import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
)
from app.modules.auth.schemas.token_schema import TokenResponse


class FakeAuthService:
    login_error = False
    refresh_error = False
    logout_error = False
    login_calls = []
    refresh_calls = []
    logout_calls = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    async def login(self, email: str, password: str):
        self.__class__.login_calls.append((email, password))
        if self.login_error:
            raise ValueError("Invalid credentials")
        return TokenResponse(access_token="access", refresh_token="refresh")

    async def refresh_session(self, refresh_token: str):
        self.__class__.refresh_calls.append(refresh_token)
        if self.refresh_error:
            raise ValueError("Invalid refresh token")
        return TokenResponse(access_token="new-access", refresh_token="new-refresh")

    async def logout_session(self, current_user, refresh_token: str | None):
        self.__class__.logout_calls.append((current_user.id, refresh_token))
        if self.logout_error:
            raise ValueError("Invalid refresh token")


class FakeGoogleOAuthService:
    authorization_error = None
    callback_error = None

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def build_authorization_url(self, state_token: str):
        if self.authorization_error is not None:
            raise self.authorization_error
        return f"https://accounts.example/auth?state={state_token}"

    async def authenticate_callback(self, code: str | None, state: str | None):
        if self.callback_error is not None:
            raise self.callback_error
        assert code == "google-code"
        assert state == "state-token"
        return TokenResponse(access_token="google-access", refresh_token="google-refresh")


class FakeTokenService:
    def create_oauth_state_token(self) -> str:
        return "state-token"


def _user():
    return SimpleNamespace(
        id=1,
        email="user@example.com",
        first_name="Ana",
        last_name="Perez",
        password_hash="secret-hash",
        refresh_tokens=[object()],
        roles=[SimpleNamespace(role=SimpleNamespace(name="Estudiante"))],
    )


@pytest.fixture(autouse=True)
def _patch_auth_dependencies(monkeypatch: pytest.MonkeyPatch):
    FakeAuthService.login_error = False
    FakeAuthService.refresh_error = False
    FakeAuthService.logout_error = False
    FakeAuthService.login_calls = []
    FakeAuthService.refresh_calls = []
    FakeAuthService.logout_calls = []
    FakeGoogleOAuthService.authorization_error = None
    FakeGoogleOAuthService.callback_error = None
    monkeypatch.setattr(auth_controller, "AuthService", FakeAuthService)
    monkeypatch.setattr(auth_controller, "GoogleOAuthService", FakeGoogleOAuthService)
    monkeypatch.setattr(auth_controller, "TokenService", FakeTokenService)


async def test_login_returns_tokens_for_valid_json_credentials() -> None:
    response = await auth_controller.login(
        credentials=LoginRequest(
            email="user@example.com",
            password="secret-password",
        ),
        db=object(),
    )

    assert response.access_token == "access"
    assert response.refresh_token == "refresh"
    assert FakeAuthService.login_calls == [("user@example.com", "secret-password")]


async def test_login_returns_401_for_invalid_credentials() -> None:
    FakeAuthService.login_error = True

    with pytest.raises(HTTPException) as exc_info:
        await auth_controller.login(
            credentials=LoginRequest(
                email="user@example.com",
                password="secret-password",
            ),
            db=object(),
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid email or password"
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


async def test_refresh_returns_401_for_invalid_refresh_token() -> None:
    FakeAuthService.refresh_error = True

    with pytest.raises(HTTPException) as exc_info:
        await auth_controller.refresh_token(
            payload=RefreshTokenRequest(refresh_token="bad-refresh"),
            db=object(),
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired refresh token"
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


async def test_logout_returns_400_for_invalid_refresh_token() -> None:
    FakeAuthService.logout_error = True

    with pytest.raises(HTTPException) as exc_info:
        await auth_controller.logout(
            current_user=_user(),
            db=object(),
            payload=LogoutRequest(refresh_token="bad-refresh"),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid refresh token"


async def test_get_me_returns_current_user_without_sensitive_fields() -> None:
    current_user = _user()

    response = await auth_controller.get_me(current_user=current_user)

    assert response.id == current_user.id
    assert response.email == current_user.email
    assert response.roles == ["Estudiante"]
    assert not hasattr(response, "password_hash")
    assert not hasattr(response, "refresh_tokens")


async def test_google_login_redirects_and_sets_http_only_state_cookie() -> None:
    response = await auth_controller.google_login()

    assert response.status_code == 307
    assert response.headers["location"] == "https://accounts.example/auth?state=state-token"
    set_cookie = response.headers["set-cookie"]
    assert "google_oauth_state=state-token" in set_cookie
    assert "HttpOnly" in set_cookie


async def test_google_callback_state_mismatch_redirects_error_and_clears_cookie() -> None:
    request = SimpleNamespace(cookies={"google_oauth_state": "expected-state"})

    response = await auth_controller.google_callback(
        request=request,
        db=object(),
        code="google-code",
        state="different-state",
    )

    assert response.status_code == 303
    assert "error=invalid_callback" in response.headers["location"]
    assert "google_oauth_state=" in response.headers["set-cookie"]


async def test_google_callback_success_redirects_token_and_clears_cookie() -> None:
    request = SimpleNamespace(cookies={"google_oauth_state": "state-token"})

    response = await auth_controller.google_callback(
        request=request,
        db=object(),
        code="google-code",
        state="state-token",
    )

    assert response.status_code == 303
    assert "token=google-access" in response.headers["location"]
    assert "google_oauth_state=" in response.headers["set-cookie"]


async def test_google_callback_service_error_redirects_error_and_clears_cookie() -> None:
    FakeGoogleOAuthService.callback_error = auth_controller.GoogleOAuthError(
        "unauthorized_domain",
        "Domain not allowed",
    )
    request = SimpleNamespace(cookies={"google_oauth_state": "state-token"})

    response = await auth_controller.google_callback(
        request=request,
        db=object(),
        code="google-code",
        state="state-token",
    )

    assert response.status_code == 303
    assert "error=unauthorized_domain" in response.headers["location"]
    assert "google_oauth_state=" in response.headers["set-cookie"]
