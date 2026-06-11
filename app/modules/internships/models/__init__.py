"""Modelos ORM del modulo de practicas."""

from app.modules.internships.models.current_state_model import CurrentState
from app.modules.internships.models.induction_model import (
    InductionAttempt,
    InductionContentVersion,
    InductionQuestion,
    InductionVideo,
)
from app.modules.internships.models.internship_model import Internship
from app.modules.internships.models.internship_status_history_model import (
    InternshipStatusHistory,
)
from app.modules.internships.models.student_internship_requirement_model import (
    StudentInternshipRequirement,
)

__all__ = [
    "CurrentState",
    "InductionAttempt",
    "InductionContentVersion",
    "InductionQuestion",
    "InductionVideo",
    "Internship",
    "InternshipStatusHistory",
    "StudentInternshipRequirement",
]
