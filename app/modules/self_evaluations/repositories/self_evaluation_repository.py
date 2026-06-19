"""Repositorio de autoevaluaciones de estudiantes."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models.role_model import Role
from app.modules.auth.models.user_model import User
from app.modules.auth.models.user_role_model import UserRole
from app.modules.internships.models.internship_model import Internship
from app.modules.self_evaluations.models.self_evaluation_model import SelfEvaluation


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SelfEvaluationRepository:
    """Encapsula persistencia de autoevaluaciones."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_internship(self, internship_id: int) -> Internship | None:
        query = (
            select(Internship)
            .where(Internship.id == internship_id)
            .options(selectinload(Internship.student), selectinload(Internship.status))
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_internship(
        self,
        internship_id: int,
    ) -> SelfEvaluation | None:
        query = select(SelfEvaluation).where(
            SelfEvaluation.internship_id == internship_id
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(self, evaluation_id: int) -> SelfEvaluation | None:
        query = select(SelfEvaluation).where(SelfEvaluation.id == evaluation_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_by_student(self, student_id: int) -> list[SelfEvaluation]:
        query = (
            select(SelfEvaluation)
            .where(SelfEvaluation.student_id == student_id)
            .order_by(SelfEvaluation.updated_at.desc(), SelfEvaluation.id.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_users_by_roles(self, role_names: set[str]) -> list[User]:
        query = (
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.name.in_(role_names), User.is_active.is_(True))
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .order_by(User.id.asc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().unique().all())

    async def save(self, evaluation: SelfEvaluation) -> SelfEvaluation:
        evaluation.updated_at = _utc_now()
        self.db.add(evaluation)
        await self.db.commit()
        await self.db.refresh(evaluation)
        return evaluation
