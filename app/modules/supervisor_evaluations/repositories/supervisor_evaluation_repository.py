"""Repositorio para invitaciones y evaluaciones de supervisores."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.internships.models import Internship
from app.modules.supervisor_evaluations.models.supervisor_evaluation_model import (
    SupervisorEvaluation,
    SupervisorEvaluationInvitation,
)


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SupervisorEvaluationRepository:
    """Encapsula persistencia de invitaciones y evaluaciones."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_internship(self, internship_id: int) -> Internship | None:
        """Obtiene una practica con estudiante y estado precargados."""

        query = (
            select(Internship)
            .where(Internship.id == internship_id)
            .options(selectinload(Internship.student), selectinload(Internship.status))
        )
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def revoke_active_invitations(self, internship_id: int) -> int:
        """Revoca invitaciones vigentes no usadas de una practica."""

        query = select(SupervisorEvaluationInvitation).where(
            SupervisorEvaluationInvitation.internship_id == internship_id,
            SupervisorEvaluationInvitation.used_at.is_(None),
            SupervisorEvaluationInvitation.revoked_at.is_(None),
        )
        result = await self.db.execute(query)
        invitations = list(result.scalars().all())

        now = _utc_now()
        for invitation in invitations:
            invitation.revoked_at = now

        return len(invitations)

    async def create_invitation(
        self,
        invitation: SupervisorEvaluationInvitation,
    ) -> SupervisorEvaluationInvitation:
        """Persiste una invitacion y confirma la transaccion."""

        self.db.add(invitation)
        await self.db.commit()
        await self.db.refresh(invitation)

        return invitation

    async def get_invitation_by_token_hash(
        self,
        token_hash: str,
    ) -> SupervisorEvaluationInvitation | None:
        """Obtiene una invitacion por hash de token."""

        query = (
            select(SupervisorEvaluationInvitation)
            .where(SupervisorEvaluationInvitation.token_hash == token_hash)
            .options(
                selectinload(SupervisorEvaluationInvitation.internship).selectinload(
                    Internship.student
                ),
                selectinload(SupervisorEvaluationInvitation.internship).selectinload(
                    Internship.status
                ),
            )
        )
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def get_evaluation_by_internship(
        self,
        internship_id: int,
    ) -> SupervisorEvaluation | None:
        """Obtiene la evaluacion asociada a una practica."""

        query = select(SupervisorEvaluation).where(
            SupervisorEvaluation.internship_id == internship_id
        )
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def create_evaluation_and_mark_invitation_used(
        self,
        evaluation: SupervisorEvaluation,
        invitation: SupervisorEvaluationInvitation,
    ) -> SupervisorEvaluation:
        """Guarda la evaluacion y marca la invitacion usada en una transaccion."""

        now = _utc_now()
        invitation.used_at = now
        evaluation.submitted_at = now
        self.db.add(evaluation)
        await self.db.commit()
        await self.db.refresh(evaluation)

        return evaluation

    async def list_internships_by_supervisor_email(
        self,
        supervisor_email: str,
    ) -> list[Internship]:
        """Lista practicas asociadas al correo del supervisor autenticado."""

        query = (
            select(Internship)
            .where(Internship.supervisor_email == supervisor_email)
            .options(selectinload(Internship.student), selectinload(Internship.status))
            .order_by(Internship.upload_date.desc(), Internship.id.desc())
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())
