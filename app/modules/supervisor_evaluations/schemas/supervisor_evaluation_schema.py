"""Schemas para consulta e ingreso de evaluaciones de supervisor externo."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


SUPERVISOR_EVALUATION_CRITERIA = [
    {
        "key": "technical_performance",
        "label": "Desempeño técnico",
        "description": "Aplica conocimientos y herramientas acordes a las tareas asignadas.",
    },
    {
        "key": "responsibility",
        "label": "Responsabilidad",
        "description": "Cumple horarios, compromisos y entregas solicitadas.",
    },
    {
        "key": "communication",
        "label": "Comunicación",
        "description": "Informa avances, dificultades y requerimientos con claridad.",
    },
    {
        "key": "teamwork",
        "label": "Trabajo en equipo",
        "description": "Se integra adecuadamente con el equipo y entorno laboral.",
    },
    {
        "key": "autonomy",
        "label": "Autonomía y aprendizaje",
        "description": "Aprende, propone soluciones y ejecuta tareas con supervisión razonable.",
    },
]
CRITERIA_KEYS = {criterion["key"] for criterion in SUPERVISOR_EVALUATION_CRITERIA}


class SupervisorEvaluationCriteriaResponse(BaseModel):
    """Criterio evaluable y escala compartida con el frontend."""

    key: str
    label: str
    description: str
    min_score: int = 1
    max_score: int = 5


class SupervisorEvaluationInvitationResponse(BaseModel):
    """Respuesta tras generar o reenviar una invitacion."""

    invitation_id: int
    internship_id: int
    supervisor_email: EmailStr
    expires_at: datetime
    revoked_previous_count: int
    demo_token: str | None = None
    demo_url: str | None = None


class SupervisorEvaluationPublicResponse(BaseModel):
    """Informacion minima visible por token publico."""

    internship_id: int
    org_name: str
    student_name: str
    internship_type: str
    start_date: date
    end_date: date
    supervisor_name: str
    criteria: list[SupervisorEvaluationCriteriaResponse]


Recommendation = Literal[
    "recommended",
    "recommended_with_observations",
    "not_recommended",
]


class SupervisorEvaluationSubmitRequest(BaseModel):
    """Payload publico de envio unico de evaluacion."""

    criteria_scores: dict[str, int]
    observations: str | None = Field(default=None, max_length=4000)
    recommendation: Recommendation

    @model_validator(mode="after")
    def validate_criteria(self) -> "SupervisorEvaluationSubmitRequest":
        provided_keys = set(self.criteria_scores.keys())
        if provided_keys != CRITERIA_KEYS:
            missing = sorted(CRITERIA_KEYS - provided_keys)
            extra = sorted(provided_keys - CRITERIA_KEYS)
            raise ValueError(
                f"Invalid evaluation criteria. missing={missing}, extra={extra}"
            )

        invalid_scores = {
            key: score
            for key, score in self.criteria_scores.items()
            if score < 1 or score > 5
        }
        if invalid_scores:
            raise ValueError("Scores must be between 1 and 5")

        return self


class SupervisorEvaluationSubmitResponse(BaseModel):
    """Respuesta tras recibir la evaluacion del supervisor."""

    evaluation_id: int
    internship_id: int
    submitted_at: datetime


class SupervisorEvaluationAdminResponse(BaseModel):
    """Evaluacion visible para estudiante propietario, Encargado y Director."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    internship_id: int
    supervisor_name_snapshot: str
    supervisor_email_snapshot: EmailStr
    criteria_scores: dict[str, int]
    observations: str | None
    recommendation: Recommendation
    status: str
    submitted_at: datetime


class SupervisorAssignmentResponse(BaseModel):
    """Practica asignada al supervisor autenticado por correo verificado."""

    internship_id: int
    org_name: str
    student_name: str
    internship_type: str
    start_date: date
    end_date: date
    status_label: str
    evaluation_submitted: bool
