from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.modules.supervisor_evaluations.schemas.supervisor_evaluation_schema import (
    CRITERIA_KEYS,
    SupervisorEvaluationSubmitRequest,
)
from app.modules.supervisor_evaluations.services.supervisor_evaluation_service import (
    SupervisorEvaluationError,
    SupervisorEvaluationService,
)


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _role(name: str):
    return SimpleNamespace(role=SimpleNamespace(name=name))


def _user(user_id: int = 1, email: str = "actor@ufrontera.cl", roles=None):
    return SimpleNamespace(
        id=user_id,
        email=email,
        roles=[_role(role) for role in (roles or ["Encargado de practica"])],
    )


def _internship(**overrides):
    data = {
        "id": 10,
        "org_name": "Acme",
        "supervisor_name": "Roberto Saez",
        "supervisor_email": "supervisor@empresa.cl",
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 2, 1),
        "internship_type": SimpleNamespace(value="Práctica de Estudio I"),
        "is_cancelled": False,
        "user_id": 5,
        "completion_status": "not_started",
        "student": SimpleNamespace(first_name="Ana", last_name="Perez"),
        "status": SimpleNamespace(title="Aprobada"),
    }
    data.update(overrides)
    return SimpleNamespace(**data)


class FakeRepository:
    def __init__(self) -> None:
        self.internship = _internship()
        self.invitation = None
        self.evaluation = None
        self.revoked_count = 0

    async def get_internship(self, internship_id: int):
        if internship_id != self.internship.id:
            return None
        return self.internship

    async def get_evaluation_by_internship(self, internship_id: int):
        return self.evaluation if internship_id == self.internship.id else None

    async def revoke_active_invitations(self, internship_id: int):
        return self.revoked_count

    async def create_invitation(self, invitation):
        invitation.id = 99
        invitation.internship = self.internship
        self.invitation = invitation
        return invitation

    async def get_invitation_by_token_hash(self, token_hash: str):
        if self.invitation and self.invitation.token_hash == token_hash:
            self.invitation.internship = self.internship
            return self.invitation
        return None

    async def create_evaluation_and_mark_invitation_used(self, evaluation, invitation):
        evaluation.id = 77
        evaluation.submitted_at = _utc_now()
        invitation.used_at = evaluation.submitted_at
        self.evaluation = evaluation
        return evaluation

    async def list_internships_by_supervisor_email(self, supervisor_email: str):
        if supervisor_email == self.internship.supervisor_email:
            return [self.internship]
        return []


class FakeNotificationService:
    def __init__(self) -> None:
        self.notifications = []

    async def create_and_dispatch(self, notification):
        self.notifications.append(notification)
        return notification


def _service(repository=None, notification_service=None, mode="simulated"):
    config = SimpleNamespace(
        NOTIFICATION_MODE=mode,
        CORS_ALLOWED_ORIGINS=["http://localhost:5173"],
    )
    return SupervisorEvaluationService(
        repository=repository or FakeRepository(),
        notification_service=notification_service,
        app_config=config,
    )


def _payload() -> SupervisorEvaluationSubmitRequest:
    return SupervisorEvaluationSubmitRequest(
        criteria_scores={key: 5 for key in CRITERIA_KEYS},
        observations="Buen desempeño",
        recommendation="recommended",
    )


async def test_generate_invitation_returns_demo_link_in_simulated_mode() -> None:
    repository = FakeRepository()
    notifications = FakeNotificationService()
    service = _service(repository=repository, notification_service=notifications)

    response = await service.generate_invitation(
        internship_id=10,
        actor=_user(),
    )

    assert response.demo_token
    assert response.demo_url.endswith(response.demo_token)
    assert response.supervisor_email == "supervisor@empresa.cl"
    assert len(notifications.notifications) == 1
    assert repository.invitation.token_hash != response.demo_token


async def test_generate_invitation_requires_approved_internship() -> None:
    repository = FakeRepository()
    repository.internship = _internship(status=SimpleNamespace(title="Pendiente"))
    service = _service(repository=repository)

    with pytest.raises(SupervisorEvaluationError) as exc_info:
        await service.generate_invitation(internship_id=10, actor=_user())

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Internship is not approved"
    assert repository.invitation is None


async def test_public_form_exposes_minimum_information_for_valid_token() -> None:
    repository = FakeRepository()
    service = _service(repository=repository)
    invitation = await service.generate_invitation(internship_id=10, actor=_user())

    response = await service.get_public_evaluation_form(invitation.demo_token)

    assert response.org_name == "Acme"
    assert response.student_name == "Ana Perez"
    assert response.supervisor_name == "Roberto Saez"
    assert len(response.criteria) == len(CRITERIA_KEYS)


async def test_public_form_rejects_invitation_when_internship_stops_being_approved() -> None:
    repository = FakeRepository()
    service = _service(repository=repository)
    invitation = await service.generate_invitation(internship_id=10, actor=_user())
    repository.internship.status = SimpleNamespace(title="Rechazada")

    with pytest.raises(SupervisorEvaluationError) as exc_info:
        await service.get_public_evaluation_form(invitation.demo_token)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Internship is not approved"


async def test_expired_invitation_is_rejected() -> None:
    repository = FakeRepository()
    service = _service(repository=repository)
    invitation = await service.generate_invitation(internship_id=10, actor=_user())
    repository.invitation.expires_at = _utc_now() - timedelta(minutes=1)

    with pytest.raises(SupervisorEvaluationError) as exc_info:
        await service.get_public_evaluation_form(invitation.demo_token)

    assert exc_info.value.status_code == 410


async def test_submit_evaluation_marks_token_used_and_prevents_reuse() -> None:
    repository = FakeRepository()
    service = _service(repository=repository)
    invitation = await service.generate_invitation(internship_id=10, actor=_user())

    response = await service.submit_public_evaluation(
        token=invitation.demo_token,
        payload=_payload(),
    )

    assert response.evaluation_id == 77
    assert repository.invitation.used_at is not None

    with pytest.raises(SupervisorEvaluationError) as exc_info:
        await service.submit_public_evaluation(
            token=invitation.demo_token,
            payload=_payload(),
        )

    assert exc_info.value.status_code == 409


@pytest.mark.parametrize("role", ["Secretaria de Carrera", "FICA"])
async def test_non_admin_role_cannot_read_supervisor_evaluation(role: str) -> None:
    repository = FakeRepository()
    repository.evaluation = SimpleNamespace(id=1, internship_id=10)
    service = _service(repository=repository)

    with pytest.raises(SupervisorEvaluationError) as exc_info:
        await service.get_evaluation_for_user(
            internship_id=10,
            actor=_user(roles=[role]),
        )

    assert exc_info.value.status_code == 403


async def test_supervisor_assignments_match_authenticated_email() -> None:
    repository = FakeRepository()
    service = _service(repository=repository)

    assignments = await service.list_assignments_for_supervisor(
        _user(
            email="supervisor@empresa.cl",
            roles=["Supervisor de practica"],
        )
    )

    assert len(assignments) == 1
    assert assignments[0].student_name == "Ana Perez"
