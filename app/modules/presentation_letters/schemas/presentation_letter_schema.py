"""Schemas HTTP para plantillas y cartas de presentacion."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PRACTICE_TYPE_VALUES = (
    "Práctica de Estudio I",
    "Práctica de Estudio II",
)
PracticeType = Literal["Práctica de Estudio I", "Práctica de Estudio II"]


class PresentationLetterTemplateUpdateRequest(BaseModel):
    """Payload para editar una plantilla de carta."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    subtitle: str = Field(min_length=1, max_length=255)
    base_intro: str = Field(min_length=1, max_length=5000)
    student_presentation_template: str = Field(min_length=1, max_length=5000)
    practice_description: str = Field(min_length=1, max_length=5000)
    minimum_hours: int = Field(ge=1, le=1000)
    learning_outcomes: list[str] = Field(min_length=1, max_length=20)
    insurance_clause: str = Field(min_length=1, max_length=5000)
    closing_text: str = Field(min_length=1, max_length=5000)
    signature_name: str = Field(min_length=1, max_length=255)
    signature_role: str = Field(min_length=1, max_length=255)
    signature_institution: str = Field(min_length=1, max_length=255)
    is_active: bool = True

    @field_validator(
        "title",
        "subtitle",
        "base_intro",
        "student_presentation_template",
        "practice_description",
        "insurance_clause",
        "closing_text",
        "signature_name",
        "signature_role",
        "signature_institution",
    )
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("El campo no puede estar vacio")
        return normalized

    @field_validator("learning_outcomes")
    @classmethod
    def normalize_learning_outcomes(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values if value.strip()]
        if not normalized:
            raise ValueError("Debe existir al menos un aprendizaje esperado")
        return normalized


class PresentationLetterTemplateResponse(BaseModel):
    """Respuesta publica de una plantilla."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    practice_type: str
    title: str
    subtitle: str
    base_intro: str
    student_presentation_template: str
    practice_description: str
    minimum_hours: int
    learning_outcomes: list[str]
    insurance_clause: str
    closing_text: str
    signature_name: str
    signature_role: str
    signature_institution: str
    is_active: bool
    created_by: int | None
    updated_by: int | None
    created_at: datetime
    updated_at: datetime


class PresentationLetterGenerateRequest(BaseModel):
    """Payload para generar automaticamente una carta."""

    model_config = ConfigDict(extra="forbid")

    practice_type: PracticeType

    @model_validator(mode="after")
    def normalize_practice_type(self) -> "PresentationLetterGenerateRequest":
        self.practice_type = self.practice_type.strip()
        return self


class PresentationLetterStudentResponse(BaseModel):
    """Datos publicos del estudiante asociado a una carta."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str
    rut: str
    cod_degree: str | None = None


class PresentationLetterResponse(BaseModel):
    """Metadata publica de una carta generada."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    practice_type: str
    template_id: int
    generated_file_name: str
    recipient_email: str
    sent_at: datetime | None
    downloaded_at: datetime | None
    created_at: datetime
    updated_at: datetime
    student: PresentationLetterStudentResponse | None = None
