"""Servicio administrativo para contenido versionado de induccion."""

from fastapi import HTTPException, status

from app.modules.internships.models.induction_model import (
    ContentStatusEnum,
    InductionContentVersion,
)
from app.modules.internships.repositories.internship_repository import (
    InternshipRepository,
)
from app.modules.internships.schemas.induction_admin_schema import (
    InductionAdminVersionPayload,
)


class InductionAdminService:
    """Orquesta CRUD administrativo y publicacion de induccion."""

    def __init__(self, repository: InternshipRepository) -> None:
        self.repository = repository

    async def list_versions(self) -> list[InductionContentVersion]:
        """Lista versiones disponibles para historial administrativo."""

        return await self.repository.list_induction_content_versions()

    async def get_version(self, version_id: int) -> InductionContentVersion:
        """Obtiene una version o falla con 404."""

        version = await self.repository.get_induction_content_version_by_id(version_id)
        if version is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontro la version de induccion solicitada.",
            )
        return version

    async def create_draft(
        self,
        payload: InductionAdminVersionPayload,
    ) -> InductionContentVersion:
        """Crea una nueva version en estado borrador."""

        videos, questions = self._build_children(payload)
        version = InductionContentVersion(
            title=payload.title,
            description=payload.description,
            min_score=payload.min_score,
            requires_retake=payload.requires_retake,
            status=ContentStatusEnum.draft,
            is_active=False,
            videos=videos,
            questions=questions,
        )

        return await self.repository.create_induction_content_version(version)

    async def update_draft(
        self,
        version_id: int,
        payload: InductionAdminVersionPayload,
    ) -> InductionContentVersion:
        """Actualiza una version solo si sigue en borrador."""

        version = await self.get_version(version_id)
        self._ensure_draft(version)
        videos, questions = self._build_children(payload)

        version.title = payload.title
        version.description = payload.description
        version.min_score = payload.min_score
        version.requires_retake = payload.requires_retake
        version.videos = videos
        version.questions = questions

        return await self.repository.update_induction_content_version(version)

    async def discard_draft(self, version_id: int) -> None:
        """Descarta una version en borrador."""

        version = await self.get_version(version_id)
        self._ensure_draft(version)
        await self.repository.delete_induction_content_version(version)

    async def publish(self, version_id: int) -> InductionContentVersion:
        """Publica o reactiva una version y la deja como unica activa."""

        version = await self.get_version(version_id)
        self._ensure_publishable(version)

        return await self.repository.publish_induction_content_version(version)

    def _ensure_draft(self, version: InductionContentVersion) -> None:
        if version.status != ContentStatusEnum.draft:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Las versiones publicadas de induccion no se pueden modificar.",
            )

    def _ensure_publishable(self, version: InductionContentVersion) -> None:
        question_count = len(version.questions or [])
        if question_count == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La version de induccion debe incluir al menos una pregunta.",
            )
        if version.min_score > question_count:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El puntaje minimo no puede superar el total de preguntas.",
            )

    def _build_children(self, payload: InductionAdminVersionPayload):
        videos_data = [video.model_dump() for video in payload.videos]
        questions_data = [question.model_dump() for question in payload.questions]
        return self.repository.build_induction_children(
            videos=videos_data,
            questions=questions_data,
        )
