from datetime import date

import pytest
from pydantic import ValidationError

from app.modules.internships.schemas.internship_schema import InternshipCreateRequest


def _valid_payload() -> dict[str, object]:
    return {
        "org_name": "Acme Chile",
        "sector": "Tecnologia",
        "address": "Av. Siempre Viva 123",
        "city": "Temuco",
        "org_phone": "+56912345678",
        "web": "https://acme.example",
        "start_date": date(2026, 6, 1),
        "end_date": date(2026, 8, 31),
        "schedule": "09:00-18:00",
        "days": "Lunes a viernes",
        "modality": "Presencial",
        "internship_address": "Av. Practica 456",
        "act_description": "Desarrollo de funcionalidades backend.",
        "ben_description": "Apoyo al equipo de plataforma.",
        "amount": 120000,
    }


def test_internship_create_request_accepts_valid_payload() -> None:
    internship = InternshipCreateRequest(**_valid_payload())

    assert internship.org_name == "Acme Chile"
    assert internship.modality == "Presencial"
    assert internship.amount == 120000


def test_internship_create_request_rejects_end_date_before_start_date() -> None:
    payload = _valid_payload()
    payload["end_date"] = date(2026, 5, 31)

    with pytest.raises(ValidationError):
        InternshipCreateRequest(**payload)


@pytest.mark.parametrize("invalid_modality", ["Online", "Híbrido", ""])
def test_internship_create_request_rejects_invalid_modality(
    invalid_modality: str,
) -> None:
    payload = _valid_payload()
    payload["modality"] = invalid_modality

    with pytest.raises(ValidationError):
        InternshipCreateRequest(**payload)


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
