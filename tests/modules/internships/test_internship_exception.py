"""Tests unitarios y de integración para el flujo de excepciones administrativas en aprobación."""

from datetime import date, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.internships.models.internship_model import (
    PracticePeriodEnum,
    PracticeTypeEnum,
)
from app.modules.internships.schemas.internship_schema import InternshipCreateRequest
from app.modules.internships.services.internship_service import (
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
        supervisor_position="Jefe de Proyectos",
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


def _student() -> SimpleNamespace:
    return SimpleNamespace(
        id=10,
        email="camila.rojas@ufromail.cl",
        first_name="Camila",
        last_name="Rojas",
        rut="11.111.111-1",
        degree="Ingenieria Civil Informatica",
    )


def _status(status_id: int, title: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=status_id,
        title=title,
        description=f"Estado {title}",
    )


def _user(user_id: int, first_name: str, last_name: str, roles: list[str] = None) -> SimpleNamespace:
    roles_list = [SimpleNamespace(role=SimpleNamespace(name=r)) for r in (roles or [])]
    return SimpleNamespace(
        id=user_id,
        email=f"{first_name.lower()}.{last_name.lower()}@ufro.cl",
        first_name=first_name,
        last_name=last_name,
        roles=roles_list
    )


def _dashboard_internship(
    internship_id: int,
    status=None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=internship_id,
        org_name="Acme Chile",
        city="Temuco",
        internship_type=PracticeTypeEnum.practice_1,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 8, 31),
        upload_date=datetime(2026, 5, 29, 12, 0, 0),
        status=status,
        student=_student(),
    )


def _academic_req(status: str) -> SimpleNamespace:
    return SimpleNamespace(status=status)


# ── Fake Repository ──────────────────────────────────────────────────────────


class FakeInternshipRepository:
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
        self.updated_insurance_status = None
        self.updated_insurance_actor_id = None
        self.updated_insurance_notes = None
        
        # Atributos de rastreo para Excepciones Administrativas
        self.created_exception_internship_id = None
        self.created_exception_rule = None
        self.created_exception_reason = None
        self.created_exception_authorized_by = None
        self.exception_by_rule = None
        self.exceptions_list = []

        self._student_requirements = {}
        self._passed_induction_for_user = {}
        self._active_induction_content = None

        # Tarea 10.20: Inicialización de diccionarios para mitigar AttributeError
        self._academic_requirements = {}
        self._exceptions_by_rule = {}

        self.states = {
            "Pendiente": _status(1, "Pendiente"),
            "En revisión": _status(2, "En revisión"),
            "Aprobada": _status(3, "Aprobada"),
            "Rechazada": _status(4, "Rechazada"),
            "En revisión DIRAE": _status(5, "En revisión DIRAE"),
        }

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

    async def get_blocking_internship_for_registration(self, **kwargs):
        return None

    async def list_dashboard_internships(self):
        return self.dashboard_internships

    async def get_state_by_title(self, title: str):
        return self.states.get(title)

    async def list_internship_status_history(self, internship_id: int):
        self.requested_internship_id = internship_id
        return self.status_history

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
        return self.exception_by_rule

    async def create_exception(self, internship_id: int, rule: str, reason: str, authorized_by: int):
        self.created_exception_internship_id = internship_id
        self.created_exception_rule = rule
        self.created_exception_reason = reason
        self.created_exception_authorized_by = authorized_by
        
        return SimpleNamespace(
            id=1,
            internship_id=internship_id,
            rule=rule,
            reason=reason,
            authorized_by=authorized_by,
            actor=_user(authorized_by, "Ana", "Director", roles=["Director de carrera"])
        )

    async def update_school_insurance_validation(
        self,
        internship,
        status,
        actor_id,
        notes=None,
    ):
        internship.insurance_status = status
        internship.insurance_validated_by = actor_id
        internship.insurance_notes = notes
        self.updated_insurance_status = status
        self.updated_insurance_actor_id = actor_id
        self.updated_insurance_notes = notes
        return internship

    async def list_exceptions(self, internship_id: int):
        return self.exceptions_list

    async def get_student_requirement(self, user_id: int, requirement: str):
        return self._student_requirements.get((user_id, requirement))

    async def is_internship_applications_disabled(self) -> bool:
        return False

    async def get_passed_induction_attempt(
        self,
        user_id: int,
        content_version_id: int | None = None,
    ):
        return self._passed_induction_for_user.get(user_id)

    async def get_active_induction_content(self):
        return self._active_induction_content

    # ── Métodos de Requisito Académico (Tarea 10.20) ─────────────────────

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


"""TESTS UNITARIOS DE FLUJOS BASE"""


@pytest.mark.asyncio
async def test_create_internship_assigns_authenticated_user_id() -> None:
    repository = FakeInternshipRepository()
    repository._student_requirements[(42, "school_insurance")] = SimpleNamespace(
        is_completed=False,
    )
    repository._student_requirements[(42, "induction")] = SimpleNamespace(
        is_completed=True,
    )
    service = InternshipService(internship_repository=repository)

    internship = await service.create_internship(
        internship_data=_valid_payload(),
        user_id=42,
    )

    assert internship is repository.created_internship
    assert internship.user_id == 42
    assert internship.status_id == 1
    assert internship.has_school_insurance is False
    assert internship.org_name == "Acme Chile"
    assert internship.supervisor_email == "ana.perez@acme.example"
    assert repository.created_initial_status.title == "Pendiente"
    assert repository.created_actor_id == 42
    assert (
        repository.created_history_reason
        == "Creación inicial de solicitud de práctica"
    )
    assert repository.created_history_metadata == {"event": "internship_created"}


@pytest.mark.asyncio
async def test_get_internship_delegates_lookup_to_repository() -> None:
    repository = FakeInternshipRepository()
    repository.internship_by_id = object()
    service = InternshipService(internship_repository=repository)

    internship = await service.get_internship(internship_id=7)

    assert internship is repository.internship_by_id
    assert repository.requested_internship_id == 7


@pytest.mark.asyncio
async def test_list_user_internships_delegates_lookup_to_repository() -> None:
    repository = FakeInternshipRepository()
    repository.internships_by_user = [object(), object()]
    service = InternshipService(internship_repository=repository)

    internships = await service.list_user_internships(user_id=42)

    assert internships == repository.internships_by_user
    assert repository.requested_user_id == 42


@pytest.mark.asyncio
async def test_list_internship_tracking_delegates_lookup_to_repository() -> None:
    repository = FakeInternshipRepository()
    repository.status_history = [object()]
    service = InternshipService(internship_repository=repository)

    history = await service.list_internship_tracking(internship_id=7)

    assert history == repository.status_history
    assert repository.requested_internship_id == 7


@pytest.mark.asyncio
async def test_transition_internship_status_updates_status_and_history() -> None:
    repository = FakeInternshipRepository()
    repository.internship_by_id = SimpleNamespace(
        id=7,
        status_id=1,
        status=_status(1, "Pendiente"),
    )
    service = InternshipService(internship_repository=repository)

    internship = await service.transition_internship_status(
        internship_id=7,
        new_status_title="En revisión",
        actor_id=99,
        reason="Inicio de revisión administrativa",
        metadata={"source": "test"},
    )

    assert internship is repository.internship_by_id
    assert internship.status_id == 2
    assert repository.updated_previous_status.title == "Pendiente"
    assert repository.updated_new_status.title == "En revisión"
    assert repository.updated_actor_id == 99
    assert repository.updated_reason == "Inicio de revisión administrativa"
    assert repository.updated_metadata == {"source": "test"}


@pytest.mark.parametrize(
    ("current_status", "new_status", "new_status_id"),
    [
        ("Pendiente", "Aprobada", 3),
        ("Pendiente", "Rechazada", 4),
        ("En revisión", "Aprobada", 3),
        ("En revisión", "Rechazada", 4),
    ],
)
@pytest.mark.asyncio
async def test_transition_internship_status_allows_non_sequential_review_matrix(
    current_status: str,
    new_status: str,
    new_status_id: int,
) -> None:
    repository = FakeInternshipRepository()
    repository.internship_by_id = SimpleNamespace(
        id=7,
        status_id=repository.states[current_status].id,
        status=repository.states[current_status],
    )
    service = InternshipService(internship_repository=repository)

    internship = await service.transition_internship_status(
        internship_id=7,
        new_status_title=new_status,
        actor_id=99,
        reason="Revisión administrativa",
    )

    assert internship is repository.internship_by_id
    assert internship.status_id == new_status_id
    assert repository.updated_previous_status.title == current_status
    assert repository.updated_new_status.title == new_status
    assert repository.updated_reason == "Revisión administrativa"


@pytest.mark.asyncio
async def test_transition_internship_status_rejects_invalid_transition() -> None:
    repository = FakeInternshipRepository()
    repository.internship_by_id = SimpleNamespace(
        id=7,
        status_id=3,
        status=_status(3, "Aprobada"),
    )
    service = InternshipService(internship_repository=repository)

    with pytest.raises(ValueError) as exc_info:
        await service.transition_internship_status(
            internship_id=7,
            new_status_title="Rechazada",
            actor_id=99,
        )

    assert "Invalid status transition from Aprobada to Rechazada" in str(exc_info.value)


@pytest.mark.asyncio
async def test_transition_internship_status_treats_reprobada_as_rejected() -> None:
    repository = FakeInternshipRepository()
    repository.internship_by_id = SimpleNamespace(
        id=7,
        status_id=4,
        status=_status(4, "Reprobada"),
    )
    service = InternshipService(internship_repository=repository)

    with pytest.raises(ValueError) as exc_info:
        await service.transition_internship_status(
            internship_id=7,
            new_status_title="Rechazada",
            actor_id=99,
        )

    assert "Invalid status transition from Rechazada to Rechazada" in str(exc_info.value)


@pytest.mark.asyncio
async def test_list_dashboard_internships_maps_null_status_as_submitted() -> None:
    repository = FakeInternshipRepository()
    repository.dashboard_internships = [_dashboard_internship(1, status=None)]
    service = InternshipService(internship_repository=repository)

    internships = await service.list_dashboard_internships()

    assert len(internships) == 1
    assert internships[0].id == 1
    assert internships[0].status == "submitted"
    assert internships[0].status_label == "Pendiente"
    assert internships[0].student is not None
    assert internships[0].student.email == "camila.rojas@ufromail.cl"


@pytest.mark.asyncio
async def test_list_dashboard_internships_filters_by_normalized_status() -> None:
    repository = FakeInternshipRepository()
    repository.dashboard_internships = [
        _dashboard_internship(1, status=_status(4, "Reprobada")),
        _dashboard_internship(2, status=_status(3, "Aprobada")),
        _dashboard_internship(3, status=_status(5, "Rechazada")),
    ]
    service = InternshipService(internship_repository=repository)

    internships = await service.list_dashboard_internships(status_filter="rejected")

    assert [internship.id for internship in internships] == [1, 3]
    assert all(internship.status == "rejected" for internship in internships)


@pytest.mark.asyncio
async def test_get_dashboard_stats_counts_normalized_statuses() -> None:
    repository = FakeInternshipRepository()
    repository.dashboard_internships = [
        _dashboard_internship(1, status=None),
        _dashboard_internship(2, status=_status(1, "Pendiente")),
        _dashboard_internship(3, status=_status(2, "En revisión")),
        _dashboard_internship(4, status=_status(3, "Aprobada")),
        _dashboard_internship(5, status=_status(4, "Rechazada")),
        _dashboard_internship(6, status=_status(5, "Reprobada")),
    ]
    service = InternshipService(internship_repository=repository)

    stats = await service.get_dashboard_stats()

    assert stats.total == 6
    assert stats.submitted == 2
    assert stats.in_review == 1
    assert stats.approved == 1
    assert stats.rejected == 2


"""TESTS DE EXCEPCIONES ADMINISTRATIVAS"""


@pytest.mark.asyncio
async def test_grant_exception_success_and_idempotency() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)
    
    actor = _user(user_id=22, first_name="Ana", last_name="Director", roles=["Director de carrera"])
    repository.internship_by_id = SimpleNamespace(
        id=7,
        status_id=1,
        status=_status(1, "Pendiente"),
    )

    exception = await service.grant_exception(
        internship_id=7,
        actor=actor,
        rule="school_insurance",
        reason="Póliza física en proceso de firma por el Director de Finanzas.",
    )

    assert exception.internship_id == 7
    assert repository.created_exception_rule == "school_insurance"
    assert repository.created_exception_reason == "Póliza física en proceso de firma por el Director de Finanzas."
    assert repository.created_exception_authorized_by == 22

    repository.exception_by_rule = exception
    second_call_exception = await service.grant_exception(
        internship_id=7,
        actor=actor,
        rule="school_insurance",
        reason="Razón alternativa no procesada.",
    )
    
    assert second_call_exception is exception


@pytest.mark.asyncio
async def test_grant_exception_rejects_invalid_rules() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)
    actor = _user(user_id=22, first_name="Ana", last_name="Director", roles=["Director de carrera"])

    with pytest.raises(HTTPException) as exc_info:
        await service.grant_exception(
            internship_id=7,
            actor=actor,
            rule="invalid_rule_name",
            reason="Prueba de fallo.",
        )
    
    assert exc_info.value.status_code == 400
    assert "no admite excepción administrativa" in exc_info.value.detail


@pytest.mark.asyncio
async def test_grant_exception_requires_privileged_role() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)
    student_actor = _user(user_id=10, first_name="Cami", last_name="Rojas", roles=["Estudiante"])

    with pytest.raises(HTTPException) as exc_info:
        await service.grant_exception(
            internship_id=7,
            actor=student_actor,
            rule="school_insurance",
            reason="Intento omitir la validación de manera autónoma.",
        )
    
    assert exc_info.value.status_code == 403
    assert "Insufficient permissions" in exc_info.value.detail


@pytest.mark.asyncio
async def test_approve_seasonal_internship_raises_409_without_insurance_or_exception() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)
    actor = _user(user_id=22, first_name="Juan", last_name="Coordinador", roles=["Encargado de practica"])
    
    repository._student_requirements[(10, "induction")] = SimpleNamespace(
        is_completed=True,
    )
    repository._student_requirements[(10, "school_insurance")] = SimpleNamespace(
        is_completed=False,
    )
    repository.internship_by_id = SimpleNamespace(
        id=7,
        user_id=10,
        org_name="Acme Chile",
        student=SimpleNamespace(email="camila.rojas@ufromail.cl"),
        status_id=2,
        status=_status(2, "En revisión"),
        internship_period=PracticePeriodEnum.summer,   # Tarea 10.20: Envoltura Enum corregida para .value
        internship_type=PracticeTypeEnum.practice_1,
        has_school_insurance=True,
    )
    repository.exception_by_rule = None

    with pytest.raises(HTTPException) as exc_info:
        await service.approve(internship_id=7, actor=actor, comment="Aprobación rápida sin controles.")
        
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["rule"] == "school_insurance"


@pytest.mark.asyncio
async def test_approve_seasonal_internship_allows_advance_with_exception_active() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)
    actor = _user(user_id=22, first_name="Juan", last_name="Coordinador", roles=["Encargado de practica"])
    
    repository._student_requirements[(10, "induction")] = SimpleNamespace(
        is_completed=True,
    )
    repository._student_requirements[(10, "school_insurance")] = SimpleNamespace(
        is_completed=False,
    )
    internship_mock = SimpleNamespace(
        id=7,
        user_id=10,
        org_name="Acme Chile",
        student=SimpleNamespace(email="camila.rojas@ufromail.cl"),
        status_id=2,
        status=_status(2, "En revisión"),
        internship_period=PracticePeriodEnum.summer,   # Tarea 10.20: Envoltura Enum corregida para .value
        internship_type=PracticeTypeEnum.practice_1,
        has_school_insurance=False,  
    )
    repository.internship_by_id = internship_mock
    repository.exception_by_rule = SimpleNamespace(id=1, rule="school_insurance")

    updated_internship = await service.approve(internship_id=7, actor=actor, comment="Aprobado con bypass de excepción")

    assert updated_internship is internship_mock
    assert repository.updated_new_status.title == "Aprobada"


"""REGLA DE NEGOCIO PARA INDUCCIÓN OBLIGATORIA (PRÁCTICA I VS II)"""


@pytest.mark.asyncio
async def test_approve_practice_1_without_induction_raises_409_absolute_block() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)
    actor = _user(user_id=22, first_name="Juan", last_name="Coordinador", roles=["Encargado de practica"])
    
    repository._student_requirements[(10, "induction")] = SimpleNamespace(
        is_completed=False,
    )
    repository._passed_induction_for_user[10] = None
    repository.internship_by_id = SimpleNamespace(
        id=8,
        user_id=10,
        status_id=1,
        status=_status(1, "Pendiente"),
        internship_period=PracticePeriodEnum.semester,
        internship_type=PracticeTypeEnum.practice_1,  
        has_school_insurance=True,                    
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.approve(internship_id=8, actor=actor, comment="Procesando Práctica I")
        
    assert exc_info.value.status_code == 409
    assert "La inducción es un requisito absoluto e inexceptuable para la Práctica de Estudio I" in exc_info.value.detail


"""REGLA DE NEGOCIO: SECUENCIALIDAD DE PRÁCTICAS"""


@pytest.mark.asyncio
async def test_grant_sequentiality_exception_success() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)
    actor = _user(user_id=22, first_name="Juan", last_name="Coordinador", roles=["Encargado de practica"])
    repository.internship_by_id = SimpleNamespace(
        id=10,
        status_id=1,
        status=_status(1, "Pendiente"),
    )

    exception = await service.grant_exception(
        internship_id=10,
        actor=actor,
        rule="sequentiality",
        reason="El estudiante cursó Práctica I en otra institución en proceso de convalidación.",
    )

    assert exception.internship_id == 10
    assert repository.created_exception_rule == "sequentiality"
    assert repository.created_exception_reason == (
        "El estudiante cursó Práctica I en otra institución en proceso de convalidación."
    )
    assert repository.created_exception_authorized_by == 22


@pytest.mark.asyncio
async def test_approve_practice_2_blocked_without_approved_practice_1() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)
    actor = _user(user_id=22, first_name="Juan", last_name="Coordinador", roles=["Encargado de practica"])

    practice_2 = SimpleNamespace(
        id=11,
        user_id=10,
        org_name="Acme Chile",
        student=SimpleNamespace(email="camila.rojas@ufromail.cl"),
        status_id=1,
        status=_status(1, "Pendiente"),
        internship_period=PracticePeriodEnum.semester,
        internship_type=PracticeTypeEnum.practice_2,
        has_school_insurance=True,
    )
    repository.internship_by_id = practice_2
    # Tarea 10.20: Seteamos el requerimiento académico como No Aprobado para activar el bloqueo oficial
    repository._academic_requirements[(10, PracticeTypeEnum.practice_1.value)] = _academic_req("Pendiente")
    repository._exceptions_by_rule[(11, "sequentiality")] = None

    with pytest.raises(HTTPException) as exc_info:
        await service.approve(internship_id=11, actor=actor, comment="Aprobando Práctica II sin Práctica I")

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["rule"] == "sequentiality"


@pytest.mark.asyncio
async def test_approve_practice_2_allowed_with_approved_practice_1() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)
    actor = _user(user_id=22, first_name="Juan", last_name="Coordinador", roles=["Encargado de practica"])

    practice_2 = SimpleNamespace(
        id=12,
        user_id=10,
        org_name="Acme Chile",
        student=SimpleNamespace(email="camila.rojas@ufromail.cl"),
        status_id=1,
        status=_status(1, "Pendiente"),
        internship_period=PracticePeriodEnum.semester,
        internship_type=PracticeTypeEnum.practice_2,
        has_school_insurance=True,
    )
    repository.internship_by_id = practice_2
    # Tarea 10.07: Inyectamos el requerimiento académico Aprobado en lugar de mapear la lista interna
    repository._academic_requirements[(10, PracticeTypeEnum.practice_1.value)] = _academic_req("Aprobada")

    updated = await service.approve(internship_id=12, actor=actor, comment="Práctica II con Práctica I aprobada")

    assert updated is practice_2
    assert repository.updated_new_status.title == "En revisión"


@pytest.mark.asyncio
async def test_approve_practice_2_allowed_with_sequentiality_exception() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)
    actor = _user(user_id=22, first_name="Juan", last_name="Coordinador", roles=["Encargado de practica"])

    practice_2 = SimpleNamespace(
        id=13,
        user_id=10,
        org_name="Acme Chile",
        student=SimpleNamespace(email="camila.rojas@ufromail.cl"),
        status_id=1,
        status=_status(1, "Pendiente"),
        internship_period=PracticePeriodEnum.semester,
        internship_type=PracticeTypeEnum.practice_2,
        has_school_insurance=True,
    )
    repository.internship_by_id = practice_2
    repository._academic_requirements[(10, PracticeTypeEnum.practice_1.value)] = _academic_req("Pendiente")
    # Tarea 10.20: Enrutamiento indexado por tupla multi-regla para levantar la restricción
    repository._exceptions_by_rule[(13, "sequentiality")] = SimpleNamespace(id=99, rule="sequentiality")

    updated = await service.approve(internship_id=13, actor=actor, comment="Práctica II con excepción")

    assert updated is practice_2
    assert repository.updated_new_status.title == "En revisión"


@pytest.mark.asyncio
async def test_approve_practice_1_not_affected_by_sequentiality() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)
    actor = _user(user_id=22, first_name="Juan", last_name="Coordinador", roles=["Encargado de practica"])

    practice_1 = SimpleNamespace(
        id=14,
        user_id=10,
        org_name="Acme Chile",
        student=SimpleNamespace(email="camila.rojas@ufromail.cl"),
        status_id=1,
        status=_status(1, "Pendiente"),
        internship_period=PracticePeriodEnum.semester,
        internship_type=PracticeTypeEnum.practice_1,
        has_school_insurance=True,
    )
    repository.internship_by_id = practice_1
    repository.internships_by_user = []
    repository._student_requirements[(10, "induction")] = SimpleNamespace(
        is_completed=True,
    )

    updated = await service.approve(internship_id=14, actor=actor, comment="Práctica I sin restricción")

    assert updated is practice_1
    assert repository.updated_new_status.title == "En revisión"


@pytest.mark.asyncio
async def test_grant_sequentiality_exception_rejects_invalid_sequentiality_rule() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)
    actor = _user(user_id=22, first_name="Ana", last_name="Director", roles=["Director de carrera"])

    with pytest.raises(HTTPException) as exc_info:
        await service.grant_exception(
            internship_id=7,
            actor=actor,
            rule="invalid_rule",
            reason="Prueba.",
        )

    assert exc_info.value.status_code == 400
    assert "no admite excepción administrativa" in exc_info.value.detail


@pytest.mark.asyncio
async def test_approve_practice_2_none_status_not_crashes() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)
    actor = _user(user_id=22, first_name="Juan", last_name="Coordinador", roles=["Encargado de practica"])

    practice_2 = SimpleNamespace(
        id=15,
        user_id=10,
        org_name="Acme Chile",
        student=SimpleNamespace(email="camila.rojas@ufromail.cl"),
        status_id=1,
        status=_status(1, "Pendiente"),
        internship_period=PracticePeriodEnum.semester,
        internship_type=PracticeTypeEnum.practice_2,
        has_school_insurance=True,
    )
    repository.internship_by_id = practice_2
    # Tarea 10.20: Simulamos que la consulta del requerimiento académico de Práctica I devuelve None
    repository._academic_requirements[(10, PracticeTypeEnum.practice_1.value)] = None
    repository._exceptions_by_rule[(15, "sequentiality")] = None

    with pytest.raises(HTTPException) as exc_info:
        await service.approve(internship_id=15, actor=actor, comment="Práctica II con práctica I sin estado")

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["rule"] == "sequentiality"


@pytest.mark.asyncio
async def test_approve_practice_2_without_induction_allows_advance() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)
    actor = _user(user_id=22, first_name="Juan", last_name="Coordinador", roles=["Encargado de practica"])
    
    internship_mock = SimpleNamespace(
        id=9,
        user_id=10,
        org_name="Acme Chile",
        student=SimpleNamespace(email="camila.rojas@ufromail.cl"),
        status_id=1,
        status=_status(1, "Pendiente"),
        internship_period=PracticePeriodEnum.semester,
        internship_type=PracticeTypeEnum.practice_2,  
        has_school_insurance=True,
    )
    repository.internship_by_id = internship_mock
    repository._academic_requirements[(10, PracticeTypeEnum.practice_1.value)] = _academic_req("Aprobada")

    updated_internship = await service.approve(internship_id=9, actor=actor, comment="Procesando Práctica II")

    assert updated_internship is internship_mock
    assert repository.updated_new_status.title == "En revisión"
    assert repository.updated_reason == "Procesando Práctica II"


"""REGLA DE NEGOCIO: ELEGIBILIDAD PARA FORMALIZAR - SECUENCIALIDAD"""


@pytest.mark.asyncio
async def test_registration_eligibility_sequentiality_blocked() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)
    repository._student_requirements[(10, "school_insurance")] = SimpleNamespace(
        is_completed=True,
    )
    repository._student_requirements[(10, "induction")] = SimpleNamespace(
        is_completed=True,
    )
    repository._passed_induction_for_user[10] = SimpleNamespace(passed=True)
    repository.internships_by_user = [
        SimpleNamespace(
            id=1, user_id=10,
            status=_status(1, "Pendiente"),
            internship_type=PracticeTypeEnum.practice_1,
            exceptions=[],
        ),
    ]

    elig = await service.get_registration_eligibility(user_id=10)

    assert elig.has_approved_practice_1 is False
    assert elig.sequentiality_blocked is True
    assert elig.has_sequentiality_exception is False
    assert elig.blocked is False  


@pytest.mark.asyncio
async def test_registration_eligibility_has_approved_practice_1() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)
    repository._student_requirements[(10, "school_insurance")] = SimpleNamespace(
        is_completed=True,
    )
    repository._student_requirements[(10, "induction")] = SimpleNamespace(
        is_completed=True,
    )
    repository._passed_induction_for_user[10] = SimpleNamespace(passed=True)
    repository.internships_by_user = [
        SimpleNamespace(
            id=1, user_id=10,
            status=_status(3, "Aprobada"),
            internship_type=PracticeTypeEnum.practice_1,
            exceptions=[],
        ),
    ]

    elig = await service.get_registration_eligibility(user_id=10)

    assert elig.has_approved_practice_1 is True
    assert elig.sequentiality_blocked is False
    assert elig.has_sequentiality_exception is False


@pytest.mark.asyncio
async def test_registration_eligibility_has_sequentiality_exception() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)
    repository._student_requirements[(10, "school_insurance")] = SimpleNamespace(
        is_completed=True,
    )
    repository._passed_induction_for_user[10] = SimpleNamespace(passed=True)
    repository.internships_by_user = [
        SimpleNamespace(
            id=1, user_id=10,
            status=_status(1, "Pendiente"),
            internship_type=PracticeTypeEnum.practice_1,
            exceptions=[SimpleNamespace(rule="sequentiality")],
        ),
    ]

    elig = await service.get_registration_eligibility(user_id=10)

    assert elig.has_approved_practice_1 is False
    assert elig.sequentiality_blocked is True
    assert elig.has_sequentiality_exception is True


@pytest.mark.asyncio
async def test_registration_eligibility_school_insurance_exception_filtered() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)
    repository._student_requirements[(10, "school_insurance")] = SimpleNamespace(
        is_completed=True,
    )
    repository._passed_induction_for_user[10] = SimpleNamespace(passed=True)
    repository.internships_by_user = [
        SimpleNamespace(
            id=1, user_id=10,
            status=_status(1, "Pendiente"),
            internship_type=PracticeTypeEnum.practice_1,
            exceptions=[SimpleNamespace(rule="sequentiality")],
        ),
    ]

    elig = await service.get_registration_eligibility(user_id=10)

    assert elig.has_school_insurance_exception is False
    assert elig.has_sequentiality_exception is True


"""REGLA DE NEGOCIO: CREACIÓN DE PRÁCTICA II SIN BLOQUEO DE SECUENCIALIDAD"""


@pytest.mark.asyncio
async def test_create_practice_2_allowed_without_approved_practice_1() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)
    repository._student_requirements[(10, "school_insurance")] = SimpleNamespace(
        is_completed=True,
    )
    repository._student_requirements[(10, "induction")] = SimpleNamespace(
        is_completed=True,
    )

    payload = _valid_payload()
    payload.internship_type = PracticeTypeEnum.practice_2

    internship = await service.create_internship(
        internship_data=payload,
        user_id=10,
    )

    assert internship is repository.created_internship
    assert internship.user_id == 10
    assert internship.status_id == 1
    assert internship.internship_type == PracticeTypeEnum.practice_2


@pytest.mark.asyncio
async def test_create_practice_2_allowed_with_active_practice_1() -> None:
    repository = FakeInternshipRepository()
    service = InternshipService(internship_repository=repository)
    repository._student_requirements[(10, "school_insurance")] = SimpleNamespace(
        is_completed=True,
    )
    repository._student_requirements[(10, "induction")] = SimpleNamespace(
        is_completed=True,
    )
    repository.internships_by_user = [
        SimpleNamespace(
            id=1, user_id=10,
            status=_status(1, "Pendiente"),
            internship_type=PracticeTypeEnum.practice_1,
            exceptions=[],
        ),
    ]

    payload = _valid_payload()
    payload.internship_type = PracticeTypeEnum.practice_2

    internship = await service.create_internship(
        internship_data=payload,
        user_id=10,
    )

    assert internship is repository.created_internship
    assert internship.internship_type == PracticeTypeEnum.practice_2
