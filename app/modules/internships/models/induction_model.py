"""Modelos ORM para el módulo de Inducción Obligatoria.

Define las entidades necesarias para gestionar el contenido versionado de
la inducción (videos, cuestionario) y los intentos del estudiante.
"""

from datetime import UTC, datetime
import enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base


class ContentStatusEnum(str, enum.Enum):
    draft = "draft"
    published = "published"


class InductionContentVersion(Base):
    """Versión del contenido de inducción obligatoria.

    Cada versión agrupa videos y preguntas de cuestionario. Solo una versión
    publicada y activa puede ser consumida por los estudiantes.

    Attributes:
        id: Identificador primario.
        title: Título descriptivo de la versión.
        description: Descripción del contenido.
        status: Estado del contenido (draft/published).
        is_active: Indica si es la versión activa actual.
        requires_retake: Indica si esta versión activa invalida cumplimientos
            anteriores y exige un nuevo intento aprobado.
        min_score: Puntaje mínimo requerido para aprobar el cuestionario.
        requires_retake: Indica si la version publicada exige repetir induccion.
        published_at: Fecha de publicación, si fue publicado.
        created_at: Fecha de creación.
        updated_at: Fecha de última actualización.
    """

    __tablename__ = "induction_content_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ContentStatusEnum] = mapped_column(
        PGEnum(
            ContentStatusEnum,
            name="content_status_enum",
            create_type=False,
        ),
        default=ContentStatusEnum.draft,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    requires_retake: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    min_score: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )

    videos = relationship(
        "InductionVideo",
        back_populates="content_version",
        cascade="all, delete-orphan",
        order_by="InductionVideo.order",
    )
    questions = relationship(
        "InductionQuestion",
        back_populates="content_version",
        cascade="all, delete-orphan",
        order_by="InductionQuestion.order",
    )


class InductionVideo(Base):
    """Video embebible asociado a una versión de contenido de inducción.

    Attributes:
        id: Identificador primario.
        content_version_id: Versión de contenido a la que pertenece.
        title: Título del video.
        video_url: URL embebible del video (YouTube, Vimeo, etc.).
        order: Orden de reproducción dentro de la versión.
    """

    __tablename__ = "induction_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_version_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("induction_content_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    video_url: Mapped[str] = mapped_column(String(500), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    content_version = relationship(
        "InductionContentVersion",
        back_populates="videos",
    )


class InductionQuestion(Base):
    """Pregunta de cuestionario asociada a una versión de contenido.

    Cada pregunta tiene opciones múltiples, una respuesta correcta y un
    orden dentro del cuestionario.

    Attributes:
        id: Identificador primario.
        content_version_id: Versión de contenido a la que pertenece.
        question_text: Enunciado de la pregunta.
        options: Diccionario con las opciones {clave: texto}.
        correct_answer: Clave de la opción correcta.
        order: Orden de la pregunta en el cuestionario.
    """

    __tablename__ = "induction_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_version_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("induction_content_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[dict] = mapped_column(JSONB, nullable=False)
    correct_answer: Mapped[str] = mapped_column(String(255), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    content_version = relationship(
        "InductionContentVersion",
        back_populates="questions",
    )


class InductionAttempt(Base):
    """Registro de un intento de cuestionario de inducción por un estudiante.

    Almacena las respuestas enviadas, el puntaje obtenido y el resultado
    (aprobado/reprobado). Un intento aprobado marca la inducción como
    cumplida para el estudiante.

    Attributes:
        id: Identificador primario.
        user_id: Estudiante que realizó el intento.
        content_version_id: Versión de contenido utilizada.
        answers: Diccionario {question_id: respuesta_seleccionada}.
        score: Puntaje obtenido.
        passed: True si el puntaje >= min_score de la versión.
        attempted_at: Fecha y hora del intento.
    """

    __tablename__ = "induction_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    content_version_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("induction_content_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    answers: Mapped[dict] = mapped_column(JSONB, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )

    student = relationship("User", foreign_keys=[user_id])
    content_version = relationship("InductionContentVersion")
