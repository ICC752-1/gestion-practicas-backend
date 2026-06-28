"""Utilidades para construir la matrícula institucional de estudiantes."""


def build_student_enrollment(student: object | None) -> str | None:
    """Construye matrícula como RUT sin formato + dos dígitos de ingreso."""

    if student is None:
        return None

    rut = getattr(student, "rut", None)
    admission_year = _get_student_admission_year(student)
    if rut is None or admission_year is None:
        return None

    rut_value = "".join(character for character in str(rut) if character.isdigit())
    year_value = "".join(
        character
        for character in str(admission_year)
        if character.isdigit()
    )
    if not rut_value or len(year_value) < 2:
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
