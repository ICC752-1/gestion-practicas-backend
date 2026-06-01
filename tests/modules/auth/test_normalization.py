import pytest

from app.modules.auth.utils.normalization import normalize_phone, normalize_rut


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("12.345.678-5", "12345678-5"),
        ("12345678-5", "12345678-5"),
        ("12.345.678-5 ", "12345678-5"),
        ("00012.345.678-5", "12345678-5"),
    ],
)
def test_normalize_rut_accepts_valid_values(raw: str, expected: str) -> None:
    assert normalize_rut(raw) == expected


@pytest.mark.parametrize("raw", ["", "123", "12.345.678-0", "11.111.111-2"])
def test_normalize_rut_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(ValueError, match="RUT invalido"):
        normalize_rut(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+56912345678", "+56912345678"),
        ("56 9 1234 5678", "+56912345678"),
        ("912345678", "+56912345678"),
        ("+1 202 555 0198", "+12025550198"),
    ],
)
def test_normalize_phone_accepts_valid_values(raw: str, expected: str) -> None:
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "123", "569123", "+569123", "abcdefgh"])
def test_normalize_phone_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(ValueError, match="Telefono invalido"):
        normalize_phone(raw)
