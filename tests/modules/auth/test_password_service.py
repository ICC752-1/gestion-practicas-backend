from app.modules.auth.services.password_service import PasswordService


def test_hash_password_returns_hash() -> None:
    service = PasswordService()

    hashed = service.hash_password("my-secret")

    assert hashed
    assert hashed != "my-secret"


def test_verify_password_accepts_valid_password() -> None:
    service = PasswordService()
    hashed = service.hash_password("my-secret")

    assert service.verify_password("my-secret", hashed)


def test_verify_password_rejects_invalid_password() -> None:
    service = PasswordService()
    hashed = service.hash_password("my-secret")

    assert not service.verify_password("wrong", hashed)
