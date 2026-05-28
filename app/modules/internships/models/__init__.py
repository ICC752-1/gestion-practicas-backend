"""Modelos ORM del modulo de practicas."""

from app.modules.internships.models.current_state_model import CurrentState
from app.modules.internships.models.internship_model import Internship
from app.modules.internships.models.student_internship_requirement_model import (
    StudentInternshipRequirement,
)

__all__ = ["CurrentState", "Internship", "StudentInternshipRequirement"]
