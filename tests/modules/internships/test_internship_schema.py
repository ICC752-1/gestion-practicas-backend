from datetime import date

import pytest
from pydantic import ValidationError

from app.modules.internships.models.internship_model import (
    PracticePeriodEnum,
    PracticeTypeEnum,
)
from app.modules.internships.schemas.internship_schema import (
    InternshipCreateRequest,
    InternshipExceptionRequest,
)


def _valid_payload() -> dict[str, object]:
    return {
        "org_name": "Acme Chile",
        "sector": "Tecnologia",
        "address": "Av. Siempre Viva 123",
        "city": "Temuco",
        "org_phone": "+56912345678",
        "web": "https://acme.example",
        "supervisor_name": "Ana Perez",
        "supervisor_profession": "Ingeniera Civil Informatica",
        "supervisor_position": "Jefa de Proyectos",
        "supervisor_department": "Tecnologia",
        "supervisor_email": "ana.perez@acme.example",
        "supervisor_phone": "+56987654321",
        "start_date": date(2026, 6, 1),
        "end_date": date(2026, 8, 31),
        "schedule": "09:00-18:00",
        "days": "Lunes a viernes",
        "modality": "Presencial",
        "internship_address": "Av. Practica 456",
        "act_description": "Desarrollo de funcionalidades backend.",
        "ben_description": "Apoyo al equipo de plataforma.",
        "amount": 120000,
        "internship_period": PracticePeriodEnum.semester,  # "Semestre"
        "internship_type": PracticeTypeEnum.practice_1,  # "Practica 1"
    }


def test_internship_create_request_accepts_valid_payload() -> None:
    internship = InternshipCreateRequest(**_valid_payload())

    assert internship.org_name == "Acme Chile"
    assert internship.modality == "Presencial"
    assert internship.supervisor_email == "ana.perez@acme.example"
    assert internship.amount == 120000
    assert internship.internship_period == "Semestre"


def test_internship_create_request_rejects_end_date_before_start_date() -> None:
    payload = _valid_payload()
    payload["end_date"] = date(2026, 5, 31)

    with pytest.raises(ValidationError):
        InternshipCreateRequest(**payload)


@pytest.mark.parametrize("invalid_modality", ["Online", "Hibrido", ""])
def test_internship_create_request_rejects_invalid_modality(
    invalid_modality: str,
) -> None:
    payload = _valid_payload()
    payload["modality"] = invalid_modality

    with pytest.raises(ValidationError):
        InternshipCreateRequest(**payload)


def test_internship_create_request_accepts_hybrid_modality_with_accent() -> None:
    payload = _valid_payload()
    payload["modality"] = "Híbrido"

    internship = InternshipCreateRequest(**payload)

    assert internship.modality == "Híbrido"


def test_internship_create_request_rejects_negative_amount() -> None:
    payload = _valid_payload()
    payload["amount"] = -1

    with pytest.raises(ValidationError):
        InternshipCreateRequest(**payload)


def test_internship_create_request_allows_optional_fields_to_be_omitted() -> None:
    payload = _valid_payload()
    payload.pop("org_phone")
    payload.pop("web")
    payload.pop("amount")

    internship = InternshipCreateRequest(**payload)

    assert internship.org_phone is None
    assert internship.web is None
    assert internship.amount is None


@pytest.mark.parametrize(
    "required_field",
    [
        "org_name",
        "sector",
        "address",
        "city",
        "supervisor_name",
        "supervisor_profession",
        "supervisor_position",
        "supervisor_department",
        "supervisor_phone",
        "schedule",
        "days",
        "internship_address",
        "act_description",
        "ben_description",
    ],
)
def test_internship_create_request_rejects_blank_required_text(
    required_field: str,
) -> None:
    payload = _valid_payload()
    payload[required_field] = ""

    with pytest.raises(ValidationError):
        InternshipCreateRequest(**payload)


def test_internship_create_request_rejects_invalid_supervisor_email() -> None:
    payload = _valid_payload()
    payload["supervisor_email"] = "not-an-email"

    with pytest.raises(ValidationError):
        InternshipCreateRequest(**payload)


def test_register_semester_ok() -> None:
    """Test: Practica semestral se acepta sin has_school_insurance (backend lo computa)."""

    payload = _valid_payload()
    payload["internship_period"] = PracticePeriodEnum.semester

    internship = InternshipCreateRequest(**payload)

    assert internship.internship_period == "Semestre"
    assert not hasattr(internship, "has_school_insurance")


def test_register_summer_no_insurance() -> None:
    """Test: El esquema ya no acepta has_school_insurance; se rechaza con ValidationError."""
    payload = _valid_payload()
    payload["internship_period"] = PracticePeriodEnum.summer
    payload["has_school_insurance"] = False

    with pytest.raises(ValidationError):
        InternshipCreateRequest(**payload)


def test_register_summer_with_insurance() -> None:
    """Test: El esquema ya no acepta has_school_insurance; se rechaza con ValidationError."""
    payload = _valid_payload()
    payload["internship_period"] = PracticePeriodEnum.summer
    payload["has_school_insurance"] = True

    with pytest.raises(ValidationError):
        InternshipCreateRequest(**payload)


@pytest.mark.parametrize(
    ("reason", "test_name"),
    [
        pytest.param("", "empty string", id="reason_empty"),
        pytest.param("   ", "whitespace only", id="reason_whitespace"),
        pytest.param(None, "null value", id="reason_none"),
    ],
)
def test_exception_request_rejects_blank_reason(reason: str | None, test_name: str) -> None:
    with pytest.raises(ValidationError):
        InternshipExceptionRequest(rule="school_insurance", reason=reason)
