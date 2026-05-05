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
