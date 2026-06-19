"""Repositorio para exportacion de datos personales."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models.user_model import User
from app.modules.data_portability.models.data_portability_model import (
    DataPortabilityRequest,
)
from app.modules.documents.models.document_model import Document, DocumentStatusEnum
from app.modules.internships.models.internship_exception_model import InternshipException
from app.modules.internships.models.internship_model import Internship
from app.modules.internships.models.internship_status_history_model import (
    InternshipStatusHistory,
)
from app.modules.self_evaluations.models.self_evaluation_model import SelfEvaluation
from app.modules.supervisor_evaluations.models.supervisor_evaluation_model import (
    SupervisorEvaluation,
)


class DataPortabilityRepository:
    """Agrupa lecturas seguras para exportar datos del titular."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_user(self, user_id: int) -> User | None:
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_internships(self, user_id: int) -> list[Internship]:
        query = (
            select(Internship)
            .where(Internship.user_id == user_id)
            .options(selectinload(Internship.status), selectinload(Internship.exceptions))
            .order_by(Internship.upload_date.desc(), Internship.id.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_status_history(
        self,
        internship_ids: list[int],
    ) -> list[InternshipStatusHistory]:
        if not internship_ids:
            return []
        query = (
            select(InternshipStatusHistory)
            .where(InternshipStatusHistory.internship_id.in_(internship_ids))
            .options(
                selectinload(InternshipStatusHistory.previous_status),
                selectinload(InternshipStatusHistory.new_status),
            )
            .order_by(
                InternshipStatusHistory.internship_id.asc(),
                InternshipStatusHistory.changed_at.asc(),
                InternshipStatusHistory.id.asc(),
            )
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_exceptions(
        self,
        internship_ids: list[int],
    ) -> list[InternshipException]:
        if not internship_ids:
            return []
        query = (
            select(InternshipException)
            .where(InternshipException.internship_id.in_(internship_ids))
            .order_by(InternshipException.authorized_at.asc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_documents(self, user_id: int) -> list[Document]:
        query = (
            select(Document)
            .where(
                Document.user_id == user_id,
                Document.deleted_at.is_(None),
                Document.status != DocumentStatusEnum.deleted,
            )
            .options(selectinload(Document.document_type))
            .order_by(Document.upload_date.desc(), Document.id.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_self_evaluations(self, user_id: int) -> list[SelfEvaluation]:
        query = (
            select(SelfEvaluation)
            .where(SelfEvaluation.student_id == user_id)
            .order_by(SelfEvaluation.updated_at.desc(), SelfEvaluation.id.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_supervisor_evaluations(
        self,
        internship_ids: list[int],
    ) -> list[SupervisorEvaluation]:
        if not internship_ids:
            return []
        query = (
            select(SupervisorEvaluation)
            .where(SupervisorEvaluation.internship_id.in_(internship_ids))
            .order_by(SupervisorEvaluation.submitted_at.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create_request(
        self,
        request: DataPortabilityRequest,
    ) -> DataPortabilityRequest:
        self.db.add(request)
        await self.db.commit()
        await self.db.refresh(request)
        return request

    async def save_request(
        self,
        request: DataPortabilityRequest,
    ) -> DataPortabilityRequest:
        self.db.add(request)
        await self.db.commit()
        await self.db.refresh(request)
        return request
