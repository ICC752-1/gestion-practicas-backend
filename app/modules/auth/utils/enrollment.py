"""Utilidades para validar y construir la matrícula institucional."""

from dataclasses import dataclass
import re

from app.modules.auth.utils.normalization import normalize_rut


MIN_ADMISSION_YEAR = 2015


@dataclass(frozen=True)
class StudentEnrollment:
    """Componentes normalizados obtenidos desde una matrícula."""

    value: str
    rut: str
    admission_year: int


def parse_student_enrollment(value: str) -> StudentEnrollment:
    """Valida una matrícula y deriva el RUT y año de ingreso."""

    if not isinstance(value, str):
        raise ValueError("La matrícula debe contener solo números")

    enrollment = value.strip()
    if not enrollment or not re.fullmatch(r"\d+", enrollment):
        raise ValueError("La matrícula debe contener solo números")
    if len(enrollment) < 4:
        raise ValueError("La matrícula está incompleta")

    rut_digits = enrollment[:-2]
    try:
        rut = normalize_rut(rut_digits)
    except ValueError as exc:
        raise ValueError(
            "El RUT contenido en la matrícula no es válido"
        ) from exc

    admission_year = 2000 + int(enrollment[-2:])
    if admission_year < MIN_ADMISSION_YEAR:
        raise ValueError(
            f"El año de ingreso no puede ser anterior a {MIN_ADMISSION_YEAR}"
        )

    return StudentEnrollment(
        value=enrollment,
        rut=rut,
        admission_year=admission_year,
    )


def build_student_enrollment(student: object | None) -> str | None:
    """Obtiene la matrícula persistida o la construye para datos históricos."""

    if student is None:
        return None

    stored_enrollment = getattr(student, "enrollment", None)
    if stored_enrollment is not None and str(stored_enrollment).strip():
        return str(stored_enrollment).strip()

    rut = getattr(student, "rut", None)
    admission_year = _get_student_admission_year(student)
    if rut is None or admission_year is None:
        return None

    rut_value = "".join(
        character
        for character in str(rut).upper()
        if character.isdigit() or character == "K"
    )
    year_value = "".join(
        character
        for character in str(admission_year)
        if character.isdigit()
    )
    if not rut_value.isdigit() or len(year_value) < 2:
        return None

    return f"{rut_value}{year_value[-2:]}"


def _get_student_admission_year(student: object) -> object | None:
    for field_name in (
        "admission_year",
        "entry_year",
        "enrollment_year",
    ):
        value = getattr(student, field_name, None)
        if value is not None:
            return value

    return None
