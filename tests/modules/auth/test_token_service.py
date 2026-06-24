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
    assert payload["type"] == "access"
    assert "exp" in payload


def test_create_refresh_token_contains_expected_claims() -> None:
    service = _service()

    token = service.create_refresh_token(subject="1")
    payload = jwt.decode(token, options={"verify_signature": False})

    assert payload["sub"] == "1"
    assert isinstance(payload["jti"], str)
    assert payload["jti"]
    assert payload["type"] == "refresh"
    assert "exp" in payload


def test_create_refresh_token_uses_provided_jti() -> None:
    service = _service()

    token = service.create_refresh_token(subject="1", jti="known-jti")
    payload = jwt.decode(token, options={"verify_signature": False})

    assert payload["jti"] == "known-jti"


def test_generate_token_jti_returns_unique_values() -> None:
    service = _service()

    first_jti = service.generate_token_jti()
    second_jti = service.generate_token_jti()

    assert first_jti != second_jti


def test_hash_token_returns_stable_hash() -> None:
    service = _service()

    first_hash = service.hash_token("refresh-token")
    second_hash = service.hash_token("refresh-token")

    assert first_hash == second_hash
    assert first_hash != "refresh-token"


def test_verify_token_hash_returns_true_for_matching_token() -> None:
    service = _service()
    token_hash = service.hash_token("refresh-token")

    assert service.verify_token_hash("refresh-token", token_hash) is True


def test_verify_token_hash_returns_false_for_different_token() -> None:
    service = _service()
    token_hash = service.hash_token("refresh-token")

    assert service.verify_token_hash("other-token", token_hash) is False



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


def test_create_oauth_state_token_contains_expected_claims() -> None:
    service = _service()

    token = service.create_oauth_state_token()
    payload = jwt.decode(token, options={"verify_signature": False})

    assert payload["sub"] == "google_oauth"
    assert payload["typ"] == "oauth_state"
    assert "nonce" in payload
    assert "exp" in payload


def test_decode_oauth_state_token_returns_payload() -> None:
    service = _service()

    token = service.create_oauth_state_token()
    payload = service.decode_oauth_state_token(token)

    assert payload["typ"] == "oauth_state"


def test_decode_token_raises_for_invalid_token() -> None:
    service = _service()

    with pytest.raises(ValueError, match="Token inválido"):
        service.decode_token("invalid-token")
