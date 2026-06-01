import jwt
import pytest

from app.modules.auth.services.token_service import TokenService


def _service() -> TokenService:
    return TokenService()


def test_create_access_token_contains_expected_claims() -> None:
    service = _service()

    token = service.create_access_token(
        subject="1",
        email="user@example.com",
        roles=["Estudiante"],
    )

    payload = jwt.decode(token, options={"verify_signature": False})

    assert payload["sub"] == "1"
    assert payload["email"] == "user@example.com"
    assert payload["roles"] == ["Estudiante"]
    assert "exp" in payload


def test_create_refresh_token_contains_expected_claims() -> None:
    service = _service()

    token = service.create_refresh_token(subject="1")
    payload = jwt.decode(token, options={"verify_signature": False})

    assert payload["sub"] == "1"
    assert "exp" in payload


def test_decode_token_returns_payload() -> None:
    service = _service()

    token = service.create_access_token(
        subject="1",
        email="user@example.com",
        roles=["Estudiante"],
    )

    payload = service.decode_token(token)

    assert payload["sub"] == "1"
    assert payload["email"] == "user@example.com"


def test_decode_token_raises_for_invalid_token() -> None:
    service = _service()

    with pytest.raises(ValueError, match="Token inválido"):
        service.decode_token("invalid-token")
