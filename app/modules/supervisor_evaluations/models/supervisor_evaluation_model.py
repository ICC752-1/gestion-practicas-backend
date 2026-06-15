"""Modelos ORM para invitaciones y evaluaciones de supervisores externos."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SupervisorEvaluationInvitation(Base):
    """Invitacion de un solo uso para que un supervisor evalue una practica."""

    __tablename__ = "supervisor_evaluation_invitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internship_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("internship.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supervisor_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    supervisor_email_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    internship = relationship("Internship")
    creator = relationship("User", foreign_keys=[created_by])


class SupervisorEvaluation(Base):
    """Evaluacion enviada por un supervisor externo para una practica."""

    __tablename__ = "supervisor_evaluations"

    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internship_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("internship.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    invitation_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("supervisor_evaluation_invitations.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
    )
    supervisor_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    supervisor_email_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    criteria_scores: Mapped[dict] = mapped_column(JSONB, nullable=False)
    observations: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="submitted", nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, nullable=False)

    internship = relationship("Internship")
    invitation = relationship("SupervisorEvaluationInvitation")
