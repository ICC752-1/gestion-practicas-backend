import pytest
from pydantic import ValidationError

from app.modules.auth.schemas.user_schema import UserCreateRequest, UserUpdateRequest


def _base_payload() -> dict[str, object]:
    return {
        "email": "user@example.com",
        "password": "my-secret-password",
        "first_name": "Ana",
        "last_name": "Perez",
        "rut": "12.345.678-5",
        "admission_year": 2023,
        "phone": "912345678",
        "sup_phone": "+56 9 8765 4321",
    }


def test_user_create_request_normalizes_rut_and_phone() -> None:
    payload = _base_payload()

    user = UserCreateRequest(**payload)

    assert user.rut == "12345678-5"
    assert user.admission_year == 2023
    assert user.phone == "+56912345678"
    assert user.sup_phone == "+56987654321"


def test_user_create_request_accepts_missing_password() -> None:
    payload = _base_payload()
    payload.pop("password")

    user = UserCreateRequest(**payload)

    assert user.password is None


def test_user_update_request_normalizes_rut_and_phone() -> None:
    payload = {
        "rut": "12.345.678-5",
        "phone": "912345678",
        "sup_phone": "+56 9 8765 4321",
    }

    user = UserUpdateRequest(**payload)

    assert user.rut == "12345678-5"
    assert user.phone == "+56912345678"
    assert user.sup_phone == "+56987654321"


@pytest.mark.parametrize("admission_year", [1899, 2101])
def test_user_create_request_rejects_invalid_admission_year(
    admission_year: int,
) -> None:
    payload = _base_payload()
    payload["admission_year"] = admission_year

    with pytest.raises(ValidationError):
        UserCreateRequest(**payload)


@pytest.mark.parametrize("field", ["rut", "phone", "sup_phone"])
def test_user_create_request_rejects_invalid_fields(field: str) -> None:
    payload = _base_payload()
    payload[field] = "invalid"

    with pytest.raises(ValidationError):
        UserCreateRequest(**payload)
