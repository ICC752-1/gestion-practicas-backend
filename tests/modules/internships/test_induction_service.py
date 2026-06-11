"""Tests unitarios para el módulo de Inducción Obligatoria y Reglas 10.20.

Cubre:
1. Consumo correcto de contenido publicado activo.
2. Intento de cuestionario aprobado versus reprobado.
3. Bloqueo de práctica estival sin seguro y aprobación con excepción.
4. Bloqueo de Práctica I por inducción incompleta.
5. Cómputo interno de has_school_insurance en create_internship.
6. Secuencialidad académica (Práctica II requiere Práctica I aprobada).
7. Secuencialidad para Tesis (requiere Práctica II aprobada o excepción).
8. Rama en paralelo para Práctica Controlada.
9. Sincronización automática de StudentInternshipRequirement al aprobar.
"""

from datetime import date, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.internships.models.internship_model import (
    PracticePeriodEnum,
    PracticeTypeEnum,
)
from app.modules.internships.schemas.internship_schema import (
    InductionAttemptRequest,
    InternshipCreateRequest,
)
from app.modules.internships.services.internship_service import (
    APPROVED_STATUS_TITLE,
    IN_REVIEW_STATUS_TITLE,
    PENDING_STATUS_TITLE,
    InternshipService,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _valid_payload() -> InternshipCreateRequest:
    return InternshipCreateRequest(
        org_name="Acme Chile",
        sector="Tecnologia",
        address="Av. Siempre Viva 123",
        city="Temuco",
        org_phone="+56912345678",
        web="https://acme.example",
        supervisor_name="Ana Perez",
        supervisor_profession="Ingeniera Civil Informatica",
        supervisor_position="Jefa de Proyectos",
        supervisor_department="Tecnologia",
        supervisor_email="ana.perez@acme.example",
        supervisor_phone="+56987654321",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 8, 31),
        schedule="09:00-18:00",
        days="Lunes a viernes",
        modality="Presencial",
        internship_address="Av. Practica 456",
        act_description="Desarrollo de funcionalidades backend.",
        ben_description="Apoyo al equipo de plataforma.",
        amount=120000,
        internship_period=PracticePeriodEnum.semester,
        internship_type=PracticeTypeEnum.practice_1,
    )


def _status(status_id: int, title: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=status_id,
        title=title,
        description=f"Estado {title}",
    )


def _make_user(*role_names: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=99,
        roles=[
            SimpleNamespace(role=SimpleNamespace(name=name))
            for name in role_names
        ],
    )


def _fake_question(q_id: int, correct: str, order: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        id=q_id,
        question_text=f"Pregunta {q_id}",
        options={"a": "Op A", "b": "Op B", "c": "Op C"},
        correct_answer=correct,
        order=order,
    )


def _fake_content(questions: list | None = None, min_score: int = 5) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        title="Inducción 2026",
        description="Contenido de prueba",
        min_score=min_score,
        videos=[],
        questions=questions or [],
    )


def _academic_req(status: str) -> SimpleNamespace:
    return SimpleNamespace(status=status)


# ── Fake Repository ──────────────────────────────────────────────────────────


class FakeInductionRepository:
    """Repositorio fake que soporta todas las operaciones de inducción y 10.20."""

    def __init__(self) -> None:
        self.created_internship = None
        self.created_initial_status = None
        self.created_actor_id = None
        self.created_history_reason = None
        self.created_history_metadata = None
        self.requested_internship_id = None
        self.requested_user_id = None
        self.internship_by_id = None
        self.internships_by_user = []
        self.dashboard_internships = []
        self.status_history = []
        self.updated_internship = None
        self.updated_previous_status = None
        self.updated_new_status = None
        self.updated_actor_id = None
        self.updated_reason = None
        self.updated_metadata = None

        self._student_requirements = {}
        self._passed_induction_for_user = {}
        self._active_induction_content = None
        self._created_attempts = []

        # (user_id, practice_type) -> SimpleNamespace(status=str)
        self._academic_requirements = {}

        # (internship_id, rule) -> SimpleNamespace or None
        self._exceptions_by_rule = {}

        self.states = {
            PENDING_STATUS_TITLE: _status(1, PENDING_STATUS_TITLE),
            IN_REVIEW_STATUS_TITLE: _status(2, IN_REVIEW_STATUS_TITLE),
            APPROVED_STATUS_TITLE: _status(3, APPROVED_STATUS_TITLE),
        }

    # ── Internship CRUD ──────────────────────────────────────────────────

    async def create_internship(self, internship):
        self.created_internship = internship
        return internship

    async def create_internship_with_history(
        self, internship, initial_status, actor_id, reason, metadata=None,
    ):
        self.created_internship = internship
        self.created_initial_status = initial_status
        self.created_actor_id = actor_id
        self.created_history_reason = reason
        self.created_history_metadata = metadata
        return internship

    async def get_internship_by_id(self, internship_id: int):
        self.requested_internship_id = internship_id
        return self.internship_by_id

    async def list_internships_by_user(self, user_id: int):
        self.requested_user_id = user_id
        return self.internships_by_user

    async def get_state_by_title(self, title: str):
        return self.states.get(title)

    async def update_internship_status_with_history(
        self, internship, previous_status, new_status, actor_id, reason, metadata=None,
    ):
        internship.status_id = new_status.id
        internship.status = new_status
        self.updated_internship = internship
        self.updated_previous_status = previous_status
        self.updated_new_status = new_status
        self.updated_actor_id = actor_id
        self.updated_reason = reason
        self.updated_metadata = metadata
        return internship

    async def get_exception_by_rule(self, internship_id: int, rule: str):
        dict_val = self._exceptions_by_rule.get((internship_id, rule))
        if dict_val is not None:
            return dict_val
        return getattr(self, "_exception_by_rule_value", None)

    # ── Prerrequisitos ───────────────────────────────────────────────────

    async def get_student_requirement(self, user_id: int, requirement: str):
        return self._student_requirements.get((user_id, requirement))

    async def get_passed_induction_attempt(self, user_id: int):
        return self._passed_induction_for_user.get(user_id)

    # ── Requisito Académico (Tarea 10.20) ────────────────────────────────

    async def get_academic_requirement(self, user_id: int, practice_type: str):
        return self._academic_requirements.get((user_id, practice_type))

    async def upsert_academic_requirement_status(
        self, user_id: int, practice_type: str, new_status: str, updated_by: int,
    ):
        existing = self._academic_requirements.get((user_id, practice_type))
        if existing is None:
            req = _academic_req(new_status)
            self._academic_requirements[(user_id, practice_type)] = req
            return req
        existing.status = new_status
        return existing

    # ── Inducción ────────────────────────────────────────────────────────

    async def get_active_induction_content(self):
        return self._active_induction_content

    async def create_induction_attempt(self, attempt):
        attempt.id = len(self._created_attempts) + 1
        attempt.attempted_at = datetime(2026, 6, 1, 12, 0, 0)
        self._created_attempts.append(attempt)
        return attempt


# ── Tests: Contenido de Inducción ────────────────────────────────────────────


class TestInductionContent:

    @pytest.mark.asyncio
    async def test_get_active_induction_content_returns_content_when_published(self):
        """1.a. Retorna contenido cuando existe versión activa publicada."""
        repo = FakeInductionRepository()
        questions = [
            _fake_question(1, "b"),
            _fake_question(2, "a"),
        ]
        repo._active_induction_content = _fake_content(questions=questions)
        service = InternshipService(internship_repository=repo)

        result = await service.get_active_induction_content()

        assert result is not None
        assert result.title == "Inducción 2026"
        assert len(result.questions) == 2
        assert result.questions[0].id == 1
        assert result.questions[0].question_text == "Pregunta 1"

    @pytest.mark.asyncio
    async def test_get_active_induction_content_returns_none_when_no_content(self):
        """1.b. Retorna None si no hay contenido activo."""
        repo = FakeInductionRepository()
        repo._active_induction_content = None
        service = InternshipService(internship_repository=repo)

        result = await service.get_active_induction_content()

        assert result is None


# ── Tests: Intento de Cuestionario ───────────────────────────────────────────


class TestInductionAttempt:

    @pytest.mark.asyncio
    async def test_submit_attempt_passes_when_score_meets_minimum(self):
        """2.a. Intento aprobado: 5 respuestas correctas de 7 (min_score=5)."""
        repo = FakeInductionRepository()
        questions = [_fake_question(i, "a", order=i) for i in range(1, 8)]
        repo._active_induction_content = _fake_content(questions=questions, min_score=5)
        service = InternshipService(internship_repository=repo)

        payload = InductionAttemptRequest(answers={i: "a" for i in range(1, 8)})
        result = await service.submit_induction_attempt(user_id=10, payload=payload)

        assert result.passed is True
        assert result.score == 7

    @pytest.mark.asyncio
    async def test_submit_attempt_fails_when_score_below_minimum(self):
        """2.b. Intento reprobado: 3 respuestas correctas de 7 (min_score=5)."""
        repo = FakeInductionRepository()
        questions = [_fake_question(i, "a", order=i) for i in range(1, 8)]
        repo._active_induction_content = _fake_content(questions=questions, min_score=5)
        service = InternshipService(internship_repository=repo)

        payload = InductionAttemptRequest(answers={i: "b" for i in range(1, 8)})
        result = await service.submit_induction_attempt(user_id=10, payload=payload)

        assert result.passed is False
        assert result.score == 0

    @pytest.mark.asyncio
    async def test_submit_attempt_fails_with_no_active_content(self):
        """2.c. Error 409 si no hay contenido activo."""
        repo = FakeInductionRepository()
        repo._active_induction_content = None
        service = InternshipService(internship_repository=repo)

        with pytest.raises(HTTPException) as exc:
            await service.submit_induction_attempt(
                user_id=10,
                payload=InductionAttemptRequest(answers={1: "a"}),
            )

        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_submit_attempt_ignores_unknown_question_ids(self):
        """2.d. Preguntas desconocidas se ignoran sin error."""
        repo = FakeInductionRepository()
        questions = [_fake_question(1, "a"), _fake_question(2, "b")]
        repo._active_induction_content = _fake_content(questions=questions, min_score=1)
        service = InternshipService(internship_repository=repo)

        payload = InductionAttemptRequest(answers={1: "a", 999: "x"})
        result = await service.submit_induction_attempt(user_id=10, payload=payload)

        assert result.passed is True
        assert result.score == 1

    @pytest.mark.asyncio
    async def test_submit_attempt_persists_attempt_record(self):
        """2.e. El intento se persiste en el repositorio."""
        repo = FakeInductionRepository()
        questions = [_fake_question(1, "a")]
        repo._active_induction_content = _fake_content(questions=questions, min_score=1)
        service = InternshipService(internship_repository=repo)

        payload = InductionAttemptRequest(answers={1: "a"})
        await service.submit_induction_attempt(user_id=10, payload=payload)

        assert len(repo._created_attempts) == 1
        assert repo._created_attempts[0].user_id == 10
        assert repo._created_attempts[0].score == 1
        assert repo._created_attempts[0].passed is True


# ── Tests: Reglas de Negocio Integradas ──────────────────────────────────────


class TestIntegratedRules:

    @pytest.mark.asyncio
    async def test_approve_seasonal_without_insurance_raises_409(self):
        """3.a. Bloqueo de práctica estival sin seguro ni excepción."""
        repo = FakeInductionRepository()
        service = InternshipService(internship_repository=repo)
        actor = _make_user("Encargado de practica")

        repo.internship_by_id = SimpleNamespace(
            id=7,
            user_id=10,
            org_name="Acme Chile",
            student=SimpleNamespace(email="test@ufro.cl"),
            status_id=1,
            status=_status(1, PENDING_STATUS_TITLE),
            internship_period=PracticePeriodEnum.summer,
            internship_type=PracticeTypeEnum.practice_2,
            has_school_insurance=False,
        )
        repo._exception_by_rule_value = None

        with pytest.raises(HTTPException) as exc:
            await service.approve(internship_id=7, actor=actor, comment=None)

        assert exc.value.status_code == 409
        assert exc.value.detail["rule"] == "school_insurance"

    @pytest.mark.asyncio
    async def test_approve_seasonal_with_exception_allows_advance(self):
        """3.b. Excepción administrativa permite avance pese a falta de seguro."""
        repo = FakeInductionRepository()
        service = InternshipService(internship_repository=repo)
        actor = _make_user("Encargado de practica")

        repo.internship_by_id = SimpleNamespace(
            id=7,
            user_id=10,
            org_name="Acme Chile",
            student=SimpleNamespace(email="test@ufro.cl"),
            status_id=1,
            status=_status(1, PENDING_STATUS_TITLE),
            internship_period=PracticePeriodEnum.summer,
            internship_type=PracticeTypeEnum.practice_2,
            has_school_insurance=False,
        )
        repo._exception_by_rule_value = SimpleNamespace(id=1, rule="school_insurance")

        result = await service.approve(internship_id=7, actor=actor, comment=None)

        assert result.status.title == IN_REVIEW_STATUS_TITLE

    @pytest.mark.asyncio
    async def test_approve_practice_1_blocked_without_induction(self):
        """4. Práctica I bloqueada si inducción está incompleta."""
        repo = FakeInductionRepository()
        service = InternshipService(internship_repository=repo)
        actor = _make_user("Encargado de practica")

        repo._student_requirements[(10, "induction")] = SimpleNamespace(
            is_completed=False,
        )
        repo._passed_induction_for_user[10] = None

        repo.internship_by_id = SimpleNamespace(
            id=8,
            user_id=10,
            org_name="Acme Chile",
            student=SimpleNamespace(email="test@ufro.cl"),
            status_id=1,
            status=_status(1, PENDING_STATUS_TITLE),
            internship_period=PracticePeriodEnum.semester,
            internship_type=PracticeTypeEnum.practice_1,
            has_school_insurance=True,
        )

        with pytest.raises(HTTPException) as exc:
            await service.approve(internship_id=8, actor=actor, comment=None)

        assert exc.value.status_code == 409
        assert "inducción" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_approve_practice_1_allowed_with_induction_completed(self):
        """4.b. Práctica I avanza si inducción está completada en backend."""
        repo = FakeInductionRepository()
        service = InternshipService(internship_repository=repo)
        actor = _make_user("Encargado de practica")

        repo._student_requirements[(10, "induction")] = SimpleNamespace(
            is_completed=True,
        )

        repo.internship_by_id = SimpleNamespace(
            id=9,
            user_id=10,
            org_name="Acme Chile",
            student=SimpleNamespace(email="test@ufro.cl"),
            status_id=1,
            status=_status(1, PENDING_STATUS_TITLE),
            internship_period=PracticePeriodEnum.semester,
            internship_type=PracticeTypeEnum.practice_1,
            has_school_insurance=True,
        )

        result = await service.approve(internship_id=9, actor=actor, comment=None)

        assert result.status.title == IN_REVIEW_STATUS_TITLE

    # ── Tarea 10.20: Secuencialidad Académica ────────────────────────────

    @pytest.mark.asyncio
    async def test_approve_practice_2_fails_without_practice_1_requirement(self):
        """6.a. Práctica II bloqueada si no hay Práctica I aprobada en StudentInternshipRequirement."""
        repo = FakeInductionRepository()
        service = InternshipService(internship_repository=repo)
        actor = _make_user("Encargado de practica")

        repo.internship_by_id = SimpleNamespace(
            id=10,
            user_id=10,
            org_name="Acme Chile",
            student=SimpleNamespace(email="test@ufro.cl"),
            status_id=1,
            status=_status(1, PENDING_STATUS_TITLE),
            internship_period=PracticePeriodEnum.semester,
            internship_type=PracticeTypeEnum.practice_2,
            has_school_insurance=True,
        )

        with pytest.raises(HTTPException) as exc:
            await service.approve(internship_id=10, actor=actor, comment=None)

        assert exc.value.status_code == 409
        assert exc.value.detail["rule"] == "sequentiality"

    @pytest.mark.asyncio
    async def test_approve_practice_2_allowed_with_practice_1_requirement(self):
        """6.b. Práctica II avanza si Práctica I está aprobada en StudentInternshipRequirement."""
        repo = FakeInductionRepository()
        service = InternshipService(internship_repository=repo)
        actor = _make_user("Encargado de practica")

        repo._academic_requirements[(10, PracticeTypeEnum.practice_1.value)] = _academic_req("Aprobada")

        repo.internship_by_id = SimpleNamespace(
            id=10,
            user_id=10,
            org_name="Acme Chile",
            student=SimpleNamespace(email="test@ufro.cl"),
            status_id=1,
            status=_status(1, PENDING_STATUS_TITLE),
            internship_period=PracticePeriodEnum.semester,
            internship_type=PracticeTypeEnum.practice_2,
            has_school_insurance=True,
        )

        result = await service.approve(internship_id=10, actor=actor, comment=None)

        assert result.status.title == IN_REVIEW_STATUS_TITLE

    @pytest.mark.asyncio
    async def test_approve_practice_2_with_sequentiality_exception(self):
        """6.c. Práctica II avanza si existe excepción de secuencialidad."""
        repo = FakeInductionRepository()
        service = InternshipService(internship_repository=repo)
        actor = _make_user("Encargado de practica")

        repo._exceptions_by_rule[(10, "sequentiality")] = SimpleNamespace(
            id=2, rule="sequentiality",
        )

        repo.internship_by_id = SimpleNamespace(
            id=10,
            user_id=10,
            org_name="Acme Chile",
            student=SimpleNamespace(email="test@ufro.cl"),
            status_id=1,
            status=_status(1, PENDING_STATUS_TITLE),
            internship_period=PracticePeriodEnum.semester,
            internship_type=PracticeTypeEnum.practice_2,
            has_school_insurance=True,
        )

        result = await service.approve(internship_id=10, actor=actor, comment=None)

        assert result.status.title == IN_REVIEW_STATUS_TITLE

    # ── Tarea 10.20: Secuencialidad para Tesis ───────────────────────────

    @pytest.mark.asyncio
    async def test_approve_thesis_fails_without_practice_2_requirement(self):
        """7.a. Tesis bloqueada si no hay Práctica II aprobada en StudentInternshipRequirement."""
        repo = FakeInductionRepository()
        service = InternshipService(internship_repository=repo)
        actor = _make_user("Encargado de practica")

        repo.internship_by_id = SimpleNamespace(
            id=11,
            user_id=10,
            org_name="Acme Chile",
            student=SimpleNamespace(email="test@ufro.cl"),
            status_id=1,
            status=_status(1, PENDING_STATUS_TITLE),
            internship_period=PracticePeriodEnum.semester,
            internship_type=PracticeTypeEnum.thesis,
            has_school_insurance=True,
        )

        with pytest.raises(HTTPException) as exc:
            await service.approve(internship_id=11, actor=actor, comment=None)

        assert exc.value.status_code == 409
        assert exc.value.detail["rule"] == "sequentiality_thesis"

    @pytest.mark.asyncio
    async def test_approve_thesis_allowed_with_practice_2_requirement(self):
        """7.b. Tesis avanza si Práctica II está aprobada en StudentInternshipRequirement."""
        repo = FakeInductionRepository()
        service = InternshipService(internship_repository=repo)
        actor = _make_user("Encargado de practica")

        repo._academic_requirements[(10, PracticeTypeEnum.practice_2.value)] = _academic_req("Aprobada")

        repo.internship_by_id = SimpleNamespace(
            id=11,
            user_id=10,
            org_name="Acme Chile",
            student=SimpleNamespace(email="test@ufro.cl"),
            status_id=1,
            status=_status(1, PENDING_STATUS_TITLE),
            internship_period=PracticePeriodEnum.semester,
            internship_type=PracticeTypeEnum.thesis,
            has_school_insurance=True,
        )

        result = await service.approve(internship_id=11, actor=actor, comment=None)

        assert result.status.title == IN_REVIEW_STATUS_TITLE

    @pytest.mark.asyncio
    async def test_approve_thesis_with_sequentiality_exception(self):
        """7.c. Tesis avanza si existe excepción sequentiality_thesis."""
        repo = FakeInductionRepository()
        service = InternshipService(internship_repository=repo)
        actor = _make_user("Encargado de practica")

        repo._exceptions_by_rule[(11, "sequentiality_thesis")] = SimpleNamespace(
            id=3, rule="sequentiality_thesis",
        )

        repo.internship_by_id = SimpleNamespace(
            id=11,
            user_id=10,
            org_name="Acme Chile",
            student=SimpleNamespace(email="test@ufro.cl"),
            status_id=1,
            status=_status(1, PENDING_STATUS_TITLE),
            internship_period=PracticePeriodEnum.semester,
            internship_type=PracticeTypeEnum.thesis,
            has_school_insurance=True,
        )

        result = await service.approve(internship_id=11, actor=actor, comment=None)

        assert result.status.title == IN_REVIEW_STATUS_TITLE

    # ── Tarea 10.20: Rama en Paralelo para Práctica Controlada ───────────

    @pytest.mark.asyncio
    async def test_approve_controlled_practice_fails_without_parallel_exception(self):
        """8.a. Práctica Controlada bloqueada sin excepción parallel_course."""
        repo = FakeInductionRepository()
        service = InternshipService(internship_repository=repo)
        actor = _make_user("Encargado de practica")

        repo.internship_by_id = SimpleNamespace(
            id=12,
            user_id=10,
            org_name="Acme Chile",
            student=SimpleNamespace(email="test@ufro.cl"),
            status_id=1,
            status=_status(1, PENDING_STATUS_TITLE),
            internship_period=PracticePeriodEnum.semester,
            internship_type=PracticeTypeEnum.controlled_practice,
            has_school_insurance=True,
        )

        with pytest.raises(HTTPException) as exc:
            await service.approve(internship_id=12, actor=actor, comment=None)

        assert exc.value.status_code == 409
        assert exc.value.detail["rule"] == "parallel_course"

    @pytest.mark.asyncio
    async def test_approve_controlled_practice_allowed_with_parallel_exception(self):
        """8.b. Práctica Controlada avanza si existe excepción parallel_course."""
        repo = FakeInductionRepository()
        service = InternshipService(internship_repository=repo)
        actor = _make_user("Encargado de practica")

        repo._exceptions_by_rule[(12, "parallel_course")] = SimpleNamespace(
            id=4, rule="parallel_course",
        )

        repo.internship_by_id = SimpleNamespace(
            id=12,
            user_id=10,
            org_name="Acme Chile",
            student=SimpleNamespace(email="test@ufro.cl"),
            status_id=1,
            status=_status(1, PENDING_STATUS_TITLE),
            internship_period=PracticePeriodEnum.semester,
            internship_type=PracticeTypeEnum.controlled_practice,
            has_school_insurance=True,
        )

        result = await service.approve(internship_id=12, actor=actor, comment=None)

        assert result.status.title == IN_REVIEW_STATUS_TITLE

    # ── Tarea 10.20: Sincronización al Aprobar ───────────────────────────

    @pytest.mark.asyncio
    async def test_approve_practice_1_syncs_academic_requirement(self):
        """9. Al aprobar Práctica I (Director), se sincroniza StudentInternshipRequirement."""
        repo = FakeInductionRepository()
        service = InternshipService(internship_repository=repo)
        actor = _make_user("Director de carrera")

        repo._student_requirements[(10, "induction")] = SimpleNamespace(
            is_completed=True,
        )

        repo.internship_by_id = SimpleNamespace(
            id=13,
            user_id=10,
            org_name="Acme Chile",
            student=SimpleNamespace(email="test@ufro.cl"),
            status_id=1,
            status=_status(1, PENDING_STATUS_TITLE),
            internship_period=PracticePeriodEnum.semester,
            internship_type=PracticeTypeEnum.practice_1,
            has_school_insurance=True,
        )

        result = await service.approve(internship_id=13, actor=actor, comment=None)

        assert result.status.title == APPROVED_STATUS_TITLE

        synced = repo._academic_requirements.get(
            (10, PracticeTypeEnum.practice_1.value),
        )
        assert synced is not None
        assert synced.status == "Aprobada"

    @pytest.mark.asyncio
    async def test_approve_practice_2_syncs_academic_requirement(self):
        """9.b. Al aprobar Práctica II (Director), se sincroniza StudentInternshipRequirement."""
        repo = FakeInductionRepository()
        service = InternshipService(internship_repository=repo)
        actor = _make_user("Director de carrera")

        repo._academic_requirements[(10, PracticeTypeEnum.practice_1.value)] = _academic_req("Aprobada")

        repo.internship_by_id = SimpleNamespace(
            id=14,
            user_id=10,
            org_name="Acme Chile",
            student=SimpleNamespace(email="test@ufro.cl"),
            status_id=1,
            status=_status(1, PENDING_STATUS_TITLE),
            internship_period=PracticePeriodEnum.semester,
            internship_type=PracticeTypeEnum.practice_2,
            has_school_insurance=True,
        )

        result = await service.approve(internship_id=14, actor=actor, comment=None)

        assert result.status.title == APPROVED_STATUS_TITLE

        synced = repo._academic_requirements.get(
            (10, PracticeTypeEnum.practice_2.value),
        )
        assert synced is not None
        assert synced.status == "Aprobada"


# ── Tests: Cómputo Interno de Seguro Escolar ─────────────────────────────────


class TestSchoolInsuranceComputation:

    @pytest.mark.asyncio
    async def test_create_sets_insurance_true_when_student_has_requirement(self):
        """5.a. has_school_insurance=True si el estudiante tiene el requisito completado."""
        repo = FakeInductionRepository()
        repo._student_requirements[(42, "school_insurance")] = SimpleNamespace(
            is_completed=True,
        )
        service = InternshipService(internship_repository=repo)

        internship = await service.create_internship(
            internship_data=_valid_payload(),
            user_id=42,
        )

        assert internship.has_school_insurance is True

    @pytest.mark.asyncio
    async def test_create_sets_insurance_false_when_student_lacks_requirement(self):
        """5.b. has_school_insurance=False si no hay requisito registrado."""
        repo = FakeInductionRepository()
        service = InternshipService(internship_repository=repo)

        internship = await service.create_internship(
            internship_data=_valid_payload(),
            user_id=42,
        )

        assert internship.has_school_insurance is False

    @pytest.mark.asyncio
    async def test_create_sets_insurance_false_when_requirement_not_completed(self):
        """5.c. has_school_insurance=False si el requisito existe pero no está completado."""
        repo = FakeInductionRepository()
        repo._student_requirements[(42, "school_insurance")] = SimpleNamespace(
            is_completed=False,
        )
        service = InternshipService(internship_repository=repo)

        internship = await service.create_internship(
            internship_data=_valid_payload(),
            user_id=42,
        )

        assert internship.has_school_insurance is False


# ── Tests: Elegibilidad ──────────────────────────────────────────────────────


class TestRegistrationEligibility:

    @pytest.mark.asyncio
    async def test_eligibility_returns_blocked_when_no_insurance_and_no_induction(self):
        """Ambos requisitos faltantes → blocked=True."""
        repo = FakeInductionRepository()
        repo._student_requirements[(10, "school_insurance")] = SimpleNamespace(
            is_completed=False,
        )
        repo._student_requirements[(10, "induction")] = SimpleNamespace(
            is_completed=False,
        )
        service = InternshipService(internship_repository=repo)

        result = await service.get_registration_eligibility(user_id=10)

        assert result.blocked is True
        assert result.has_school_insurance is False
        assert result.has_induction is False

    @pytest.mark.asyncio
    async def test_eligibility_returns_not_blocked_when_all_met(self):
        """Ambos requisitos cumplidos → blocked=False."""
        repo = FakeInductionRepository()
        repo._student_requirements[(10, "school_insurance")] = SimpleNamespace(
            is_completed=True,
        )
        repo._student_requirements[(10, "induction")] = SimpleNamespace(
            is_completed=True,
        )
        service = InternshipService(internship_repository=repo)

        result = await service.get_registration_eligibility(user_id=10)

        assert result.blocked is False
        assert result.has_school_insurance is True
        assert result.has_induction is True

    @pytest.mark.asyncio
    async def test_eligibility_uses_passed_induction_attempt_as_fallback(self):
        """Inducción aprobada vía InductionAttempt si no hay StudentRegistrationRequirement."""
        repo = FakeInductionRepository()
        repo._student_requirements[(10, "school_insurance")] = SimpleNamespace(
            is_completed=True,
        )
        repo._passed_induction_for_user[10] = SimpleNamespace(passed=True)
        service = InternshipService(internship_repository=repo)

        result = await service.get_registration_eligibility(user_id=10)

        assert result.blocked is False
        assert result.has_induction is True
