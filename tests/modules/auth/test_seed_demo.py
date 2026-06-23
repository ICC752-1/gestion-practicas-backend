import pytest

from scripts.seed_demo import (
    DEMO_ACADEMIC_REQUIREMENTS,
    DEMO_USERS,
    DEMO_INDUCTION_TITLE,
    INDUCTION_CORRECT_ANSWER,
    INDUCTION_OPTIONS,
    STUDENT_DEMO_EMAIL,
    STUDENT_OTHER_EMAIL,
    UNSUPPORTED_DEMO_SCENARIOS,
    _ensure_not_production,
    _get_demo_password,
)


def test_seed_demo_requires_password(monkeypatch) -> None:
    monkeypatch.delenv("DEMO_SEED_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="DEMO_SEED_PASSWORD is required"):
        _get_demo_password()


def test_seed_demo_rejects_short_password(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_SEED_PASSWORD", "short")

    with pytest.raises(RuntimeError, match="at least 8"):
        _get_demo_password()


def test_seed_demo_rejects_production_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(RuntimeError, match="disabled in production"):
        _ensure_not_production()


def test_seed_demo_allows_local_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")

    _ensure_not_production()


def test_seed_demo_student_emails_use_institutional_domain() -> None:
    student_emails = [
        user["email"]
        for user in DEMO_USERS
        if user["first_name"] == "Estudiante"
    ]

    assert student_emails == [
        "estudiante.demo@ufromail.cl",
        "estudiante.otro@ufromail.cl",
        "estudiante.activo@ufromail.cl",
    ]


def test_seed_demo_induction_uses_stable_answer_keys() -> None:
    assert INDUCTION_OPTIONS == {
        "accept": "Entiendo y acepto",
        "reject": "No acepto",
    }
    assert INDUCTION_CORRECT_ANSWER == "accept"


def test_seed_demo_uses_single_named_active_induction() -> None:
    assert DEMO_INDUCTION_TITLE == "Induccion demo QA publicada"


def test_seed_demo_sets_coherent_academic_requirements() -> None:
    assert DEMO_ACADEMIC_REQUIREMENTS[STUDENT_DEMO_EMAIL] == {
        "Práctica de Estudio I": "Aprobada",
        "Práctica de Estudio II": "Habilitada",
        "Tesis": "Pendiente",
        "Práctica Controlada": "Pendiente",
    }
    assert DEMO_ACADEMIC_REQUIREMENTS[STUDENT_OTHER_EMAIL] == {
        "Práctica de Estudio I": "Pendiente",
        "Práctica de Estudio II": "Pendiente",
        "Tesis": "Pendiente",
        "Práctica Controlada": "Pendiente",
    }


def test_seed_demo_declares_uncovered_scenarios() -> None:
    assert "agenda de entrevistas" in UNSUPPORTED_DEMO_SCENARIOS
    assert "dirae_status separado" in UNSUPPORTED_DEMO_SCENARIOS
