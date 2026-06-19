"""Schemas administrativos para administrar contenido versionado de induccion."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class InductionAdminVideoPayload(BaseModel):
    """Video editable de una version de induccion."""

    title: str = Field(min_length=1, max_length=255)
    video_url: str = Field(min_length=8, max_length=500)
    order: int = Field(ge=0)

    @field_validator("video_url")
    @classmethod
    def validate_video_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("video_url must be an absolute HTTP(S) URL")
        return value


class InductionAdminQuestionPayload(BaseModel):
    """Pregunta editable de una version de induccion."""

    question_text: str = Field(min_length=1)
    options: dict[str, str]
    correct_answer: str = Field(min_length=1, max_length=255)
    order: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_question(self) -> "InductionAdminQuestionPayload":
        if len(self.options) < 2:
            raise ValueError("Each question must have at least two options")

        blank_options = [key for key, value in self.options.items() if not value.strip()]
        if blank_options:
            raise ValueError("Question options cannot be blank")

        if self.correct_answer not in self.options:
            raise ValueError("correct_answer must match one option key")

        return self


class InductionAdminVersionPayload(BaseModel):
    """Payload para crear o editar un borrador de induccion."""

    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    min_score: int = Field(ge=1)
    requires_retake: bool = False
    videos: list[InductionAdminVideoPayload] = Field(default_factory=list)
    questions: list[InductionAdminQuestionPayload] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_version(self) -> "InductionAdminVersionPayload":
        video_orders = [video.order for video in self.videos]
        if len(video_orders) != len(set(video_orders)):
            raise ValueError("Video order values must be unique")

        question_orders = [question.order for question in self.questions]
        if len(question_orders) != len(set(question_orders)):
            raise ValueError("Question order values must be unique")

        if self.min_score > len(self.questions):
            raise ValueError("min_score cannot exceed the number of questions")

        return self


class InductionAdminVideoResponse(BaseModel):
    """Video en detalle administrativo."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    video_url: str
    order: int


class InductionAdminQuestionResponse(BaseModel):
    """Pregunta en detalle administrativo, incluida respuesta correcta."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    question_text: str
    options: dict[str, str]
    correct_answer: str
    order: int


class InductionAdminVersionSummaryResponse(BaseModel):
    """Resumen de una version para historial administrativo."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: str
    is_active: bool
    min_score: int
    requires_retake: bool
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InductionAdminVersionDetailResponse(InductionAdminVersionSummaryResponse):
    """Detalle administrativo completo de una version."""

    description: str | None
    videos: list[InductionAdminVideoResponse]
    questions: list[InductionAdminQuestionResponse]
