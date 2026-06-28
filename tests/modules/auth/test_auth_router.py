from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response

from app.core.config import config
from app.modules.auth.controllers import auth_controller
from app.modules.auth.schemas.auth_schema import (
    ActivateAccountRequest,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
)
from app.modules.auth.schemas.token_schema import TokenResponse
from app.modules.auth.services.auth_service import (
    AccountActivationError,
    TemporaryPasswordChangeRequiredError,
)


class FakeAuthService:
    login_error = None
    refresh_error = False
    logout_error = False
    activation_error = None
    activation_info_error = None
    login_calls = []
    refresh_calls = []
    logout_calls = []
    activation_calls = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    async def login(self, email: str, password: str):
        self.__class__.login_calls.append((email, password))
        if self.login_error is not None:
            raise self.login_error
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

    async def activate_account(
        self,
        token: str,
        new_password: str,
        phone: str | None = None,
        sexo: str | None = None,
    ):
        self.__class__.activation_calls.append((token, new_password, phone, sexo))
        if self.activation_error is not None:
            raise self.activation_error

    async def get_activation_account_info(self, token: str):
        if self.activation_info_error is not None:
            raise self.activation_info_error
        return {
            "email": "user@example.com",
            "first_name": "Ana",
            "last_name": "Perez",
            "roles": ["Estudiante"],
            "enrollment": "12345678524",
            "admission_year": 2024,
            "phone": None,
            "sexo": "No definido",
        }


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


def _set_cookie_headers(response) -> str:
    return "\n".join(
        value.decode()
        for name, value in response.raw_headers
        if name.lower() == b"set-cookie"
    )


@pytest.fixture(autouse=True)
def _patch_auth_dependencies(monkeypatch: pytest.MonkeyPatch):
    FakeAuthService.login_error = None
    FakeAuthService.refresh_error = False
    FakeAuthService.logout_error = False
    FakeAuthService.activation_error = None
    FakeAuthService.activation_info_error = None
    FakeAuthService.login_calls = []
    FakeAuthService.refresh_calls = []
    FakeAuthService.logout_calls = []
    FakeAuthService.activation_calls = []
    FakeGoogleOAuthService.authorization_error = None
    FakeGoogleOAuthService.callback_error = None
    monkeypatch.setattr(auth_controller, "AuthService", FakeAuthService)
    monkeypatch.setattr(auth_controller, "GoogleOAuthService", FakeGoogleOAuthService)
    monkeypatch.setattr(auth_controller, "TokenService", FakeTokenService)


async def test_login_returns_tokens_and_sets_refresh_cookie() -> None:
    response = Response()

    token_response = await auth_controller.login(
        credentials=LoginRequest(
            email="user@example.com",
            password="secret-password",
        ),
        db=object(),
        response=response,
    )

    assert token_response.access_token == "access"
    assert token_response.refresh_token == "refresh"
    assert FakeAuthService.login_calls == [("user@example.com", "secret-password")]
    set_cookie = response.headers["set-cookie"]
    assert f"{config.REFRESH_TOKEN_COOKIE_NAME}=refresh" in set_cookie
    assert "HttpOnly" in set_cookie


async def test_login_returns_401_for_invalid_credentials() -> None:
    FakeAuthService.login_error = ValueError("Invalid credentials")

    with pytest.raises(HTTPException) as exc_info:
        await auth_controller.login(
            credentials=LoginRequest(
                email="user@example.com",
                password="secret-password",
            ),
            db=object(),
            response=Response(),
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid email or password"
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


async def test_login_returns_403_for_temporary_password() -> None:
    FakeAuthService.login_error = TemporaryPasswordChangeRequiredError()

    with pytest.raises(HTTPException) as exc_info:
        await auth_controller.login(
            credentials=LoginRequest(
                email="user@example.com",
                password="secret-password",
            ),
            db=object(),
            response=Response(),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "TEMPORARY_PASSWORD_CHANGE_REQUIRED"


async def test_refresh_uses_body_token_and_sets_new_cookie() -> None:
    response = Response()

    token_response = await auth_controller.refresh_token(
        db=object(),
        response=response,
        payload=RefreshTokenRequest(refresh_token="body-refresh"),
    )

    assert token_response.access_token == "new-access"
    assert FakeAuthService.refresh_calls == ["body-refresh"]
    assert f"{config.REFRESH_TOKEN_COOKIE_NAME}=new-refresh" in response.headers[
        "set-cookie"
    ]


async def test_refresh_uses_cookie_when_body_token_is_missing() -> None:
    await auth_controller.refresh_token(
        db=object(),
        response=Response(),
        refresh_token_cookie="cookie-refresh",
        payload=RefreshTokenRequest(refresh_token=None),
    )

    assert FakeAuthService.refresh_calls == ["cookie-refresh"]


async def test_refresh_returns_401_for_missing_or_invalid_token() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await auth_controller.refresh_token(db=object(), response=Response())

    assert exc_info.value.status_code == 401
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


async def test_logout_revokes_refresh_token_and_clears_cookie() -> None:
    response = await auth_controller.logout(
        current_user=_user(),
        db=object(),
        payload=LogoutRequest(refresh_token="body-refresh"),
    )

    assert response.status_code == 204
    assert FakeAuthService.logout_calls == [(1, "body-refresh")]
    assert f"{config.REFRESH_TOKEN_COOKIE_NAME}=" in response.headers["set-cookie"]


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


async def test_activate_account_delegates_and_maps_activation_errors() -> None:
    response = await auth_controller.activate_account(
        payload=ActivateAccountRequest(
            token="x" * 32,
            new_password="new-password",
            phone="912345678",
            sexo="Femenino",
        ),
        db=object(),
    )

    assert response.status_code == 204
    assert FakeAuthService.activation_calls == [
        ("x" * 32, "new-password", "+56912345678", "Femenino")
    ]

    FakeAuthService.activation_error = AccountActivationError("Invalid or expired")
    with pytest.raises(HTTPException) as exc_info:
        await auth_controller.activate_account(
            payload=ActivateAccountRequest(token="x" * 32, new_password="new-password"),
            db=object(),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid or expired"


async def test_activation_info_returns_data_and_maps_activation_errors() -> None:
    info = await auth_controller.get_activation_info(db=object(), token="x" * 32)

    assert info.email == "user@example.com"
    assert info.roles == ["Estudiante"]

    FakeAuthService.activation_info_error = AccountActivationError("Invalid or expired")
    with pytest.raises(HTTPException) as exc_info:
        await auth_controller.get_activation_info(db=object(), token="x" * 32)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid or expired"


async def test_google_login_redirects_and_sets_http_only_state_cookie() -> None:
    response = await auth_controller.google_login()

    assert response.status_code == 307
    assert response.headers["location"] == "https://accounts.example/auth?state=state-token"
    set_cookie = response.headers["set-cookie"]
    assert f"{config.GOOGLE_STATE_COOKIE_NAME}=state-token" in set_cookie
    assert "HttpOnly" in set_cookie


async def test_google_callback_state_mismatch_redirects_error_and_clears_cookie() -> None:
    request = SimpleNamespace(cookies={config.GOOGLE_STATE_COOKIE_NAME: "expected-state"})

    response = await auth_controller.google_callback(
        request=request,
        db=object(),
        code="google-code",
        state="different-state",
    )

    assert response.status_code == 303
    assert "error=invalid_callback" in response.headers["location"]
    assert f"{config.GOOGLE_STATE_COOKIE_NAME}=" in response.headers["set-cookie"]


async def test_google_callback_success_redirects_token_and_sets_refresh_cookie() -> None:
    request = SimpleNamespace(cookies={config.GOOGLE_STATE_COOKIE_NAME: "state-token"})

    response = await auth_controller.google_callback(
        request=request,
        db=object(),
        code="google-code",
        state="state-token",
    )

    assert response.status_code == 303
    assert "token=google-access" in response.headers["location"]
    set_cookie = _set_cookie_headers(response)
    assert f"{config.REFRESH_TOKEN_COOKIE_NAME}=google-refresh" in set_cookie
    assert f"{config.GOOGLE_STATE_COOKIE_NAME}=" in set_cookie


async def test_google_callback_service_error_redirects_error_and_clears_cookie() -> None:
    FakeGoogleOAuthService.callback_error = auth_controller.GoogleOAuthError(
        "unauthorized_domain",
        "Domain not allowed",
    )
    request = SimpleNamespace(cookies={config.GOOGLE_STATE_COOKIE_NAME: "state-token"})

    response = await auth_controller.google_callback(
        request=request,
        db=object(),
        code="google-code",
        state="state-token",
    )

    assert response.status_code == 303
    assert "error=unauthorized_domain" in response.headers["location"]
    assert f"{config.GOOGLE_STATE_COOKIE_NAME}=" in response.headers["set-cookie"]
