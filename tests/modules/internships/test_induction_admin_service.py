from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.documents.models.document_model import Document  # noqa: F401
from app.modules.internships.models.induction_model import (
    ContentStatusEnum,
    InductionQuestion,
    InductionVideo,
)
from app.modules.internships.schemas.induction_admin_schema import (
    InductionAdminQuestionResponse,
    InductionAdminVersionPayload,
)
from app.modules.internships.schemas.internship_schema import InductionQuestionResponse
from app.modules.internships.services.induction_admin_service import (
    InductionAdminService,
)
from app.modules.internships.controllers.induction_admin_controller import (
    INDUCTION_ADMIN_ROLES,
)


def _user(*roles: str):
    return SimpleNamespace(
        id=1,
        roles=[SimpleNamespace(role=SimpleNamespace(name=role)) for role in roles],
    )


def _version(status=ContentStatusEnum.draft, version_id: int = 1, is_active=False):
    return SimpleNamespace(
        id=version_id,
        title="Induccion",
        description="Demo",
        min_score=1,
        requires_retake=False,
        status=status,
        is_active=is_active,
        videos=[],
        questions=[SimpleNamespace(order=1)],
        published_at=None,
        created_at=datetime.now(UTC).replace(tzinfo=None),
        updated_at=datetime.now(UTC).replace(tzinfo=None),
    )


class FakeRepository:
    def __init__(self) -> None:
        self.version = _version()
        self.created = None
        self.updated = None
        self.deleted = None
        self.published = None

    async def list_induction_content_versions(self):
        return [self.version]

    async def get_induction_content_version_by_id(self, version_id: int):
        return self.version if version_id == self.version.id else None

    async def create_induction_content_version(self, version):
        version.id = 2
        self.created = version
        return version

    async def update_induction_content_version(self, version):
        self.updated = version
        return version

    async def delete_induction_content_version(self, version):
        self.deleted = version

    async def publish_induction_content_version(self, version):
        version.status = ContentStatusEnum.published
        version.is_active = True
        self.published = version
        return version

    def build_induction_children(self, *, videos, questions):
        return (
            [InductionVideo(**video) for video in videos],
            [InductionQuestion(**question) for question in questions],
        )


def _payload() -> InductionAdminVersionPayload:
    return InductionAdminVersionPayload(
        title="Induccion nueva",
        description="Contenido actualizado",
        min_score=1,
        requires_retake=False,
        videos=[
            {
                "title": "Video 1",
                "video_url": "https://example.com/video",
                "order": 1,
            }
        ],
        questions=[
            {
                "question_text": "Pregunta",
                "options": {"a": "Si", "b": "No"},
                "correct_answer": "a",
                "order": 1,
            }
        ],
    )


@pytest.mark.parametrize(
    "role",
    ["Encargado de practica", "Director de carrera"],
)
async def test_induction_admin_roles_are_authorized(role: str) -> None:
    dependency = require_roles(INDUCTION_ADMIN_ROLES)

    result = await dependency(_user(role))

    assert result.roles[0].role.name == role


@pytest.mark.parametrize(
    "role",
    ["Secretaria de Carrera", "Estudiante", "Supervisor de practica", "Superadmin"],
)
async def test_induction_admin_rejects_non_authorized_roles(role: str) -> None:
    dependency = require_roles(INDUCTION_ADMIN_ROLES)

    with pytest.raises(HTTPException) as exc_info:
        await dependency(_user(role))

    assert exc_info.value.status_code == 403


def test_payload_rejects_correct_answer_outside_options() -> None:
    with pytest.raises(ValueError):
        InductionAdminVersionPayload(
            title="Induccion",
            min_score=1,
            questions=[
                {
                    "question_text": "Pregunta",
                    "options": {"a": "Si", "b": "No"},
                    "correct_answer": "c",
                    "order": 1,
                }
            ],
        )


def test_payload_rejects_min_score_greater_than_question_count() -> None:
    with pytest.raises(ValueError):
        InductionAdminVersionPayload(
            title="Induccion",
            min_score=2,
            questions=[
                {
                    "question_text": "Pregunta",
                    "options": {"a": "Si", "b": "No"},
                    "correct_answer": "a",
                    "order": 1,
                }
            ],
        )


def test_payload_rejects_video_url_with_user_facing_message() -> None:
    with pytest.raises(ValueError) as exc_info:
        InductionAdminVersionPayload(
            title="Induccion",
            min_score=1,
            videos=[
                {
                    "title": "Video",
                    "video_url": "www.example.com/video",
                    "order": 1,
                }
            ],
            questions=[
                {
                    "question_text": "Pregunta",
                    "options": {"a": "Si", "b": "No"},
                    "correct_answer": "a",
                    "order": 1,
                }
            ],
        )

    assert "La URL del video debe ser completa" in str(exc_info.value)


def test_student_induction_question_response_does_not_expose_correct_answer() -> None:
    question = InductionQuestion(
        id=1,
        question_text="Pregunta",
        options={"a": "Si", "b": "No"},
        correct_answer="a",
        order=1,
    )

    response = InductionQuestionResponse.model_validate(question)

    assert "correct_answer" not in response.model_dump()


def test_admin_induction_question_response_exposes_correct_answer() -> None:
    question = InductionQuestion(
        id=1,
        question_text="Pregunta",
        options={"a": "Si", "b": "No"},
        correct_answer="a",
        order=1,
    )

    response = InductionAdminQuestionResponse.model_validate(question)

    assert response.correct_answer == "a"


async def test_create_draft_persists_structured_content() -> None:
    repository = FakeRepository()
    service = InductionAdminService(repository)

    version = await service.create_draft(_payload())

    assert repository.created is version
    assert version.status == ContentStatusEnum.draft
    assert version.videos[0].video_url == "https://example.com/video"
    assert version.questions[0].correct_answer == "a"


async def test_update_published_version_is_rejected() -> None:
    repository = FakeRepository()
    repository.version.status = ContentStatusEnum.published
    service = InductionAdminService(repository)

    with pytest.raises(HTTPException) as exc_info:
        await service.update_draft(1, _payload())

    assert exc_info.value.status_code == 409


async def test_publish_marks_version_active() -> None:
    repository = FakeRepository()
    service = InductionAdminService(repository)

    version = await service.publish(1)

    assert repository.published is version
    assert version.status == ContentStatusEnum.published
    assert version.is_active is True


async def test_publish_reactivates_published_version() -> None:
    repository = FakeRepository()
    repository.version.status = ContentStatusEnum.published
    repository.version.is_active = False
    service = InductionAdminService(repository)

    version = await service.publish(1)

    assert repository.published is version
    assert version.status == ContentStatusEnum.published
    assert version.is_active is True
