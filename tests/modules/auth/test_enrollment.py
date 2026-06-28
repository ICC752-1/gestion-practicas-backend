import pytest

from app.modules.auth.utils.enrollment import (
    build_student_enrollment,
    parse_student_enrollment,
)


def test_parse_student_enrollment_derives_rut_and_admission_year() -> None:
    enrollment = parse_student_enrollment("12345678523")

    assert enrollment.value == "12345678523"
    assert enrollment.rut == "12345678-5"
    assert enrollment.admission_year == 2023


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("12.345.678-5-23", "solo números"),
        ("12345678423", "RUT contenido"),
        ("12345678514", "anterior a 2015"),
    ],
)
def test_parse_student_enrollment_rejects_invalid_components(
    value: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        parse_student_enrollment(value)


def test_build_student_enrollment_prefers_persisted_value() -> None:
    student = type(
        "Student",
        (),
        {
            "enrollment": "98765432125",
            "rut": "12345678-5",
            "admission_year": 2023,
        },
    )()

    assert build_student_enrollment(student) == "98765432125"


def test_build_student_enrollment_keeps_historical_fallback() -> None:
    student = type(
        "Student",
        (),
        {
            "enrollment": None,
            "rut": "12.345.678-5",
            "admission_year": 2023,
        },
    )()

    assert build_student_enrollment(student) == "12345678523"
