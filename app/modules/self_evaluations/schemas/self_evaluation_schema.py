"""Contratos HTTP para autoevaluaciones de estudiantes."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.self_evaluations.models.self_evaluation_model import (
    SelfEvaluationStatusEnum,
)

SELF_EVALUATION_FORM_VERSION = "student-self-evaluation-v1"
SELF_EVALUATION_SCALE = {
    "min_score": 1,
    "max_score": 5,
    "options": [
        {"value": 1, "label": "Deficiente"},
        {"value": 2, "label": "Insuficiente"},
        {"value": 3, "label": "Suficiente"},
        {"value": 4, "label": "Bueno"},
        {"value": 5, "label": "Muy Bueno"},
    ],
}
SELF_EVALUATION_CRITERIA = [
    {
        "key": "communication",
        "section": "RA1",
        "label": "Comunicación respetuosa y efectiva",
        "description": "Me comunico con supervisor y equipo de forma respetuosa y clara.",
        "required": True,
    },
    {
        "key": "teamwork",
        "section": "RA1",
        "label": "Integración al equipo",
        "description": "Participo colaborativamente en equipos y actividades de la organización.",
        "required": True,
    },
    {
        "key": "organization_understanding",
        "section": "RA2",
        "label": "Comprensión organizacional",
        "description": "Reconozco estructura, jerarquías y procedimientos de la unidad.",
        "required": True,
    },
    {
        "key": "process_understanding",
        "section": "RA3",
        "label": "Comprensión de procesos",
        "description": "Comprendo procesos, implicancias técnicas y contexto de mis tareas.",
        "required": True,
    },
    {
        "key": "risk_prevention",
        "section": "RA4",
        "label": "Prevención de riesgos y cuidado del entorno",
        "description": "Mantengo una conducta responsable en seguridad y cuidado del entorno.",
        "required": True,
    },
    {
        "key": "ethics",
        "section": "RA5",
        "label": "Conducta ética",
        "description": "Resguardo información y actúo éticamente durante la práctica.",
        "required": True,
    },
    {
        "key": "learning_application",
        "section": "RA5",
        "label": "Aplicación de aprendizajes",
        "description": "Aplico mi formación académica en las actividades realizadas.",
        "required": True,
    },
]
CRITERIA_KEYS = {criterion["key"] for criterion in SELF_EVALUATION_CRITERIA}
REQUIRED_CRITERIA_KEYS = {
    criterion["key"] for criterion in SELF_EVALUATION_CRITERIA if criterion["required"]
}


class SelfEvaluationCriterionResponse(BaseModel):
    key: str
    section: str
    label: str
    description: str
    required: bool


class SelfEvaluationScaleResponse(BaseModel):
    min_score: int
    max_score: int
    options: list[dict[str, int | str]]


class SelfEvaluationInternshipSummary(BaseModel):
    id: int
    org_name: str
    internship_type: str
    start_date: date
    end_date: date
    completion_status: str
    final_result: str


class SelfEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    internship_id: int
    student_id: int
    form_version: str
    criteria_snapshot: list[dict]
    responses: dict[str, int]
    observations: str | None
    status: SelfEvaluationStatusEnum
    submitted_at: datetime | None
    reopened_at: datetime | None
    reopened_by: int | None
    reopen_reason: str | None
    created_at: datetime
    updated_at: datetime


class SelfEvaluationFormResponse(BaseModel):
    internship: SelfEvaluationInternshipSummary
    form_version: str
    scale: SelfEvaluationScaleResponse
    criteria: list[SelfEvaluationCriterionResponse]
    enabled: bool
    status: Literal["not_enabled", "not_started", "draft", "submitted", "reopened"]
    reason: str | None = None
    evaluation: SelfEvaluationResponse | None = None


class SelfEvaluationDraftRequest(BaseModel):
    responses: dict[str, int] = Field(default_factory=dict)
    observations: str | None = Field(default=None, max_length=4000)
    expected_updated_at: datetime | None = None

    @model_validator(mode="after")
    def validate_partial_responses(self) -> "SelfEvaluationDraftRequest":
        _validate_response_keys_and_scores(self.responses, require_all=False)
        return self


class SelfEvaluationSubmitRequest(BaseModel):
    responses: dict[str, int]
    observations: str | None = Field(default=None, max_length=4000)
    expected_updated_at: datetime | None = None

    @model_validator(mode="after")
    def validate_required_responses(self) -> "SelfEvaluationSubmitRequest":
        _validate_response_keys_and_scores(self.responses, require_all=True)
        return self


class SelfEvaluationReopenRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


def _validate_response_keys_and_scores(
    responses: dict[str, int],
    *,
    require_all: bool,
) -> None:
    provided_keys = set(responses.keys())
    extra = sorted(provided_keys - CRITERIA_KEYS)
    if extra:
        raise ValueError(f"Invalid self-evaluation criteria. extra={extra}")

    if require_all:
        missing = sorted(REQUIRED_CRITERIA_KEYS - provided_keys)
        if missing:
            raise ValueError(f"Missing required criteria. missing={missing}")

    min_score = SELF_EVALUATION_SCALE["min_score"]
    max_score = SELF_EVALUATION_SCALE["max_score"]
    invalid_scores = {
        key: score
        for key, score in responses.items()
        if score < min_score or score > max_score
    }
    if invalid_scores:
        raise ValueError("Scores must be between 1 and 5")
