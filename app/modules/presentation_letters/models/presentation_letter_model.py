"""Modelos ORM para cartas de presentacion generadas desde plantillas."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class PresentationLetterTemplate(Base):
    """Plantilla editable por tipo de practica."""

    __tablename__ = "presentation_letter_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    practice_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subtitle: Mapped[str] = mapped_column(String(255), nullable=False)
    base_intro: Mapped[str] = mapped_column(Text, nullable=False)
    student_presentation_template: Mapped[str] = mapped_column(Text, nullable=False)
    practice_description: Mapped[str] = mapped_column(Text, nullable=False)
    minimum_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=168)
    minimum_hours_clause: Mapped[str] = mapped_column(Text, nullable=False)
    learning_outcomes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    insurance_clause: Mapped[str] = mapped_column(Text, nullable=False)
    closing_text: Mapped[str] = mapped_column(Text, nullable=False)
    signature_name: Mapped[str] = mapped_column(String(255), nullable=False)
    signature_role: Mapped[str] = mapped_column(String(255), nullable=False)
    signature_institution: Mapped[str] = mapped_column(String(255), nullable=False)
    signature_image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )
    updated_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_now,
        onupdate=_now,
        nullable=False,
    )

    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])

    @property
    def signature_image_uploaded(self) -> bool:
        """Indica si la plantilla tiene una imagen de firma administrada."""

        return bool(self.signature_image_path)

    __table_args__ = (
        Index(
            "uq_presentation_letter_template_active_type",
            "practice_type",
            unique=True,
            postgresql_where=is_active.is_(True),
        ),
        Index("ix_presentation_letter_template_type", "practice_type"),
    )


class PresentationLetter(Base):
    """Carta PDF generada automaticamente para un estudiante."""

    __tablename__ = "presentation_letter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )
    practice_type: Mapped[str] = mapped_column(String(100), nullable=False)
    template_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("presentation_letter_template.id"),
        nullable=False,
    )
    generated_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    generated_file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_now,
        onupdate=_now,
        nullable=False,
    )

    student = relationship("User", foreign_keys=[student_id])
    template = relationship("PresentationLetterTemplate", foreign_keys=[template_id])

    __table_args__ = (
        Index("ix_presentation_letter_student", "student_id"),
        Index("ix_presentation_letter_practice_type", "practice_type"),
        Index("ix_presentation_letter_template", "template_id"),
    )
