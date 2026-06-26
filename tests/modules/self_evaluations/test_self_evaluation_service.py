from datetime import date, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.documents.models.document_model import Document as _Document
from app.modules.self_evaluations.models.self_evaluation_model import (
    SelfEvaluationStatusEnum,
)
from app.modules.self_evaluations.schemas.self_evaluation_schema import (
    SelfEvaluationDraftRequest,
    SelfEvaluationReopenRequest,
    SelfEvaluationSubmitRequest,
)
from app.modules.self_evaluations.services.self_evaluation_service import (
    SelfEvaluationService,
)


_REGISTER_DOCUMENT_MODEL = _Document


class FakeSelfEvaluationRepository:
    def __init__(self) -> None:
        self.internship = _internship()
        self.evaluation = None
        self.saved = None
        self.by_id = {}

    async def get_internship(self, internship_id: int):
        return self.internship if self.internship.id == internship_id else None

    async def get_by_internship(self, internship_id: int):
        return self.evaluation if self.evaluation and self.evaluation.internship_id == internship_id else None

    async def get_by_id(self, evaluation_id: int):
        return self.by_id.get(evaluation_id)

    async def list_by_student(self, student_id: int):
        if self.evaluation and self.evaluation.student_id == student_id:
            return [self.evaluation]
        return []

    async def save(self, evaluation):
        if getattr(evaluation, "id", None) is None:
            evaluation.id = 1
            evaluation.created_at = datetime(2026, 6, 18, 10, 0, 0)
        evaluation.updated_at = datetime(2026, 6, 18, 11, 0, 0)
        self.evaluation = evaluation
        self.by_id[evaluation.id] = evaluation
        self.saved = evaluation
        return evaluation


def _role(name: str) -> SimpleNamespace:
    return SimpleNamespace(role=SimpleNamespace(name=name))


def _user(user_id: int = 10, *roles: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        email="juan.perez@correo.cl",
        roles=[_role(role) for role in roles],
    )


def _internship(
    *,
    user_id: int = 10,
    status_title: str = "Aprobada",
    completion_status: str = "pending_evaluations",
    end_date: date = date(2026, 6, 1),
) -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        user_id=user_id,
        org_name="Empresa Demo",
        internship_type=SimpleNamespace(value="Práctica de Estudio I"),
        start_date=date(2026, 3, 1),
        end_date=end_date,
        completion_status=completion_status,
        final_result="pending",
        is_cancelled=False,
        status=SimpleNamespace(title=status_title),
        student=SimpleNamespace(email="juan.perez@correo.cl"),
    )


async def test_form_is_not_enabled_for_fresh_internship() -> None:
    repository = FakeSelfEvaluationRepository()
    repository.internship = _internship(
        completion_status="in_progress",
        end_date=date(2099, 6, 1),
    )
    service = SelfEvaluationService(repository)

    form = await service.get_form(internship_id=7, actor=_user(10, "Estudiante"))

    assert form.enabled is False
    assert form.status == "not_enabled"
    assert (
        form.reason
        == "La autoevaluación se habilita desde los últimos 5 días hábiles de la práctica"
    )


async def test_form_is_enabled_during_last_five_business_days() -> None:
    internship = _internship(
        completion_status="in_progress",
        end_date=date(2026, 6, 17),
    )

    enabled, reason = SelfEvaluationService._is_enabled(
        internship,
        today=date(2026, 6, 11),
    )

    assert enabled is True
    assert reason is None


async def test_form_is_not_enabled_before_last_five_business_days() -> None:
    internship = _internship(
        completion_status="in_progress",
        end_date=date(2026, 6, 17),
    )

    enabled, reason = SelfEvaluationService._is_enabled(
        internship,
        today=date(2026, 6, 10),
    )

    assert enabled is False
    assert (
        reason
        == "La autoevaluación se habilita desde los últimos 5 días hábiles de la práctica"
    )


async def test_save_draft_persists_partial_responses() -> None:
    repository = FakeSelfEvaluationRepository()
    service = SelfEvaluationService(repository)

    evaluation = await service.save_draft(
        internship_id=7,
        actor=_user(10, "Estudiante"),
        payload=SelfEvaluationDraftRequest(
            responses={"communication": 4},
            observations="Buen avance",
        ),
    )

    assert evaluation.status == SelfEvaluationStatusEnum.draft
    assert evaluation.responses == {"communication": 4}
    assert evaluation.student_id == 10


async def test_submit_requires_owner_and_locks_evaluation() -> None:
    repository = FakeSelfEvaluationRepository()
    service = SelfEvaluationService(repository)

    with pytest.raises(HTTPException) as error:
        await service.submit(
            internship_id=7,
            actor=_user(99, "Estudiante"),
            payload=SelfEvaluationSubmitRequest(
                responses={
                    "communication": 4,
                    "teamwork": 4,
                    "organization_understanding": 4,
                    "process_understanding": 4,
                    "risk_prevention": 4,
                    "ethics": 4,
                    "learning_application": 4,
                },
            ),
        )

    assert error.value.status_code == 403


async def test_submitted_evaluation_cannot_be_edited_without_reopen() -> None:
    repository = FakeSelfEvaluationRepository()
    service = SelfEvaluationService(repository)
    await service.submit(
        internship_id=7,
        actor=_user(10, "Estudiante"),
        payload=SelfEvaluationSubmitRequest(
            responses={
                "communication": 5,
                "teamwork": 5,
                "organization_understanding": 5,
                "process_understanding": 5,
                "risk_prevention": 5,
                "ethics": 5,
                "learning_application": 5,
            },
        ),
    )

    with pytest.raises(HTTPException) as error:
        await service.save_draft(
            internship_id=7,
            actor=_user(10, "Estudiante"),
            payload=SelfEvaluationDraftRequest(responses={"communication": 3}),
        )

    assert error.value.status_code == 409


async def test_admin_reopen_requires_reason_and_records_actor() -> None:
    repository = FakeSelfEvaluationRepository()
    service = SelfEvaluationService(repository)
    evaluation = await service.submit(
        internship_id=7,
        actor=_user(10, "Estudiante"),
        payload=SelfEvaluationSubmitRequest(
            responses={
                "communication": 5,
                "teamwork": 4,
                "organization_understanding": 4,
                "process_understanding": 4,
                "risk_prevention": 5,
                "ethics": 5,
                "learning_application": 4,
            },
        ),
    )

    reopened = await service.reopen(
        evaluation_id=evaluation.id,
        actor=_user(20, "Director de carrera"),
        payload=SelfEvaluationReopenRequest(reason="Corrección solicitada por comité"),
    )

    assert reopened.status == SelfEvaluationStatusEnum.reopened
    assert reopened.reopened_by == 20
    assert reopened.reopen_reason == "Corrección solicitada por comité"
