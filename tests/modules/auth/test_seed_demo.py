import pytest

from app.modules.auth.utils.enrollment import parse_student_enrollment
from scripts.seed_demo import (
    DEMO_ACADEMIC_REQUIREMENTS,
    DEMO_USERS,
    DEMO_INDUCTION_TITLE,
    INDUCTION_CORRECT_ANSWER,
    INDUCTION_OPTIONS,
    REALISTIC_FINAL_PRACTICE_OPTIONS,
    REALISTIC_PRACTICE_REQUIREMENT_ORDER,
    STUDENT_DEMO_EMAIL,
    STUDENT_OTHER_EMAIL,
    UNSUPPORTED_DEMO_SCENARIOS,
    _build_realistic_practice_plan,
    _build_realistic_requirement_statuses,
    _ensure_not_production,
    _get_demo_password,
    _make_student_identity,
)
from app.modules.internships.models.internship_model import (
    FinalResultEnum,
    PracticeTypeEnum,
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


def test_seed_demo_students_have_valid_persisted_enrollment() -> None:
    students = [
        user
        for user in DEMO_USERS
        if user["first_name"] == "Estudiante"
    ]

    for student in students:
        parsed = parse_student_enrollment(student["enrollment"])

        assert parsed.rut == student["rut"]
        assert parsed.admission_year == student["admission_year"]


def test_seed_demo_generated_students_use_numeric_rut_in_enrollment() -> None:
    identity = _make_student_identity(22000001, 2022)

    assert identity.rut != "22000001-K"
    assert identity.value.isdigit()
    assert identity.value.endswith("22")


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


def test_realistic_seed_practice_plans_follow_academic_order() -> None:
    for index in range(1, 61):
        plan = _build_realistic_practice_plan(index, active=index % 7 != 0)
        completed_previous = set(plan.completed_previous)

        if plan.current_type == PracticeTypeEnum.practice_2:
            assert PracticeTypeEnum.practice_1 in completed_previous

        if plan.current_type in REALISTIC_FINAL_PRACTICE_OPTIONS:
            assert completed_previous == {
                PracticeTypeEnum.practice_1,
                PracticeTypeEnum.practice_2,
            }


def test_realistic_seed_marks_only_one_final_practice_option() -> None:
    for index in range(1, 61):
        plan = _build_realistic_practice_plan(index, active=True)
        statuses = _build_realistic_requirement_statuses(
            plan,
            FinalResultEnum.passed,
        )
        selected_finals = [
            practice_type
            for practice_type in REALISTIC_FINAL_PRACTICE_OPTIONS
            if statuses[practice_type] != "Pendiente"
        ]

        assert len(selected_finals) <= 1
        assert list(statuses) == list(REALISTIC_PRACTICE_REQUIREMENT_ORDER)


def test_seed_demo_declares_only_current_uncovered_edges() -> None:
    unsupported = set(UNSUPPORTED_DEMO_SCENARIOS)

    assert "agenda con entrevista, presentacion final y conflicto horario" in unsupported
    assert "solicitud de carta pendiente y carta emitida" in unsupported
    assert "autoevaluacion" not in unsupported
    assert "invitaciones de supervisor" not in unsupported
    assert "dirae_status separado" not in unsupported
