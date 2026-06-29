"""Siembra datos demo idempotentes para QA local.

Uso local/Docker:
    DEMO_SEED_PASSWORD=demo-password uv run python scripts/seed_demo.py
    DEMO_SEED_PASSWORD=demo-password uv run python scripts/seed_demo.py --clean
    DEMO_SEED_PASSWORD=demo-password uv run python scripts/seed_demo.py --only users --only induction
    DEMO_SEED_PASSWORD=demo-password uv run python scripts/seed_demo.py --bulk-students 250
    DEMO_SEED_PASSWORD=demo-password uv run python scripts/seed_demo.py --realista
    uv run python scripts/seed_demo.py --reset-admin-only
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import delete, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.database import SessionLocal
from app.modules.auth.models.role_model import Role
from app.modules.auth.models.user_model import User
from app.modules.auth.models.user_role_model import UserRole
from app.modules.auth.services.password_service import PasswordService
from app.modules.auth.utils.enrollment import (
    StudentEnrollment,
    parse_student_enrollment,
)
from app.modules.auth.utils.roles import (
    CAREER_DIRECTOR_ROLE,
    FICA_ROLE,
    PRACTICE_MANAGER_ROLE,
    SECRETARY_ROLE,
    STUDENT_ROLE,
    SUPERADMIN_ROLE,
    SUPERVISOR_ROLE,
    SYSTEM_ROLE_NAMES,
)
from app.modules.documents.models.document_model import Document, DocumentType
from app.modules.internships.models.current_state_model import CurrentState
from app.modules.internships.models.induction_model import (
    ContentStatusEnum,
    InductionAttempt,
    InductionContentVersion,
    InductionQuestion,
    InductionVideo,
)
from app.modules.internships.models.internship_exception_model import (
    ExceptableRule,
    InternshipException,
)
from app.modules.internships.models.internship_model import (
    CompletionStatusEnum,
    FinalResultEnum,
    Internship,
    PracticePeriodEnum,
    PracticeTypeEnum,
    SchoolInsuranceStatusEnum,
)
from app.modules.internships.models.internship_status_history_model import (
    InternshipStatusHistory,
)
from app.modules.internships.models.student_internship_requirement_model import (
    RegistrationRequirementType,
    StudentInternshipRequirement,
    StudentRegistrationRequirement,
)
from app.modules.notifications.models.notification_model import (
    Notification,
    NotificationEventTypeEnum,
    NotificationStatusEnum,
)


STUDENT_DEMO_EMAIL = "estudiante.demo@ufromail.cl"
STUDENT_OTHER_EMAIL = "estudiante.otro@ufromail.cl"
STUDENT_ACTIVE_EMAIL = "estudiante.activo@ufromail.cl"
LEGACY_DEMO_EMAILS = ("estudiante.demo@correo.cl", "estudiante.otro@correo.cl")
INDUCTION_OPTIONS = {"accept": "Entiendo y acepto", "reject": "No acepto"}
INDUCTION_CORRECT_ANSWER = "accept"
DEMO_INDUCTION_TITLE = "Induccion demo QA publicada"
DEFAULT_ADMIN_EMAIL = "superadmin@ufrontera.cl"
BULK_STUDENT_EMAIL_PREFIX = "qa.estudiante."
REALISTIC_STUDENT_EMAIL_PREFIX = "realista.estudiante."
DEFAULT_REALISTIC_STUDENT_COUNT = 120
DEFAULT_SCENARIOS = {
    "users",
    "induction",
    "requirements",
    "internships",
    "notifications",
}
VALID_SCENARIOS = {"base", *DEFAULT_SCENARIOS, "all"}
BASE_STATES = (
    (
        "Pendiente",
        "La solicitud de práctica existe como estado del proceso, pero aún no inicia su tramitación en el sistema.",
    ),
    (
        "En revisión DIRAE",
        "La solicitud de práctica presenta observaciones en sus plazos y fue derivada a la Dirección de Registro Académico y Estudiantil.",
    ),
    (
        "En revisión",
        "La solicitud de práctica fue registrada y se encuentra en revisión administrativa.",
    ),
    (
        "Aprobada",
        "La solicitud de práctica fue aprobada durante la revisión administrativa.",
    ),
    (
        "Rechazada",
        "La solicitud de práctica fue rechazada durante la revisión administrativa.",
    ),
)
BASE_DOCUMENT_TYPES = (
    (
        "Formulario de inscripción",
        "Formulario de inscripción de práctica firmado o respaldado.",
        False,
        "Académico",
        False,
    ),
    (
        "Carta de aceptación",
        "Documento emitido por la organización receptora.",
        False,
        "Administrativo",
        False,
    ),
    (
        "Seguro escolar",
        "Respaldo administrativo de cobertura cuando corresponda.",
        False,
        "Administrativo",
        True,
    ),
    (
        "Documento complementario",
        "Documento adicional requerido para regularizar o respaldar el caso.",
        False,
        "Administrativo",
        False,
    ),
    (
        "Diapositivas de Presentación",
        "Material de apoyo o diapositivas para la presentación final.",
        False,
        "Académico",
        False,
    ),
)
ROLE_DESCRIPTIONS = {
    STUDENT_ROLE: "Rol correspondiente a estudiantes en practicas",
    SUPERVISOR_ROLE: "Rol correspondiente al supervisor externo de practicas",
    PRACTICE_MANAGER_ROLE: "Rol correspondiente al encargado de practicas",
    CAREER_DIRECTOR_ROLE: "Rol correspondiente al director de carrera",
    SECRETARY_ROLE: "Rol correspondiente a secretaria de carrera",
    FICA_ROLE: "Rol institucional de consulta agregada transversal",
    SUPERADMIN_ROLE: "Rol tecnico para administracion de usuarios y roles",
}
LONG_DEMO_NOTIFICATION_SUBJECT = (
    "Notificacion de prueba con asunto muy largo para validar la visualizacion "
    "completa en la campana de notificaciones del estudiante"
)
LONG_DEMO_NOTIFICATION_CONTENT = (
    "Este mensaje fue generado por seed_demo.py para validar que la campana de "
    "notificaciones pueda mostrar textos extensos sin perder informacion relevante. "
    "Debe permitir al estudiante comprender el contexto completo de la solicitud de "
    "practica, incluyendo que la notificacion puede contener instrucciones largas, "
    "fechas importantes, responsabilidades del estudiante y referencias al flujo de "
    "seguimiento dentro de la plataforma."
)
DEMO_ACADEMIC_REQUIREMENTS = {
    STUDENT_DEMO_EMAIL: {
        PracticeTypeEnum.practice_1.value: "Aprobada",
        PracticeTypeEnum.practice_2.value: "Habilitada",
        PracticeTypeEnum.thesis.value: "Pendiente",
        PracticeTypeEnum.controlled_practice.value: "Pendiente",
    },
    STUDENT_OTHER_EMAIL: {
        PracticeTypeEnum.practice_1.value: "Pendiente",
        PracticeTypeEnum.practice_2.value: "Pendiente",
        PracticeTypeEnum.thesis.value: "Pendiente",
        PracticeTypeEnum.controlled_practice.value: "Pendiente",
    },
}
UNSUPPORTED_DEMO_SCENARIOS = (
    "agenda con entrevista, presentacion final y conflicto horario",
    "invitaciones de supervisor revocadas y expiradas",
    "solicitud de carta pendiente y carta emitida",
    "version de induccion en borrador",
    "eventos de auditoria transversales",
    "paquete DIRAE no exportable y expediente observado",
)


def _make_rut(body: int) -> str:
    reversed_digits = map(int, reversed(str(body)))
    factors = (2, 3, 4, 5, 6, 7)
    total = 0
    for index, digit in enumerate(reversed_digits):
        total += digit * factors[index % len(factors)]
    value = 11 - (total % 11)
    if value == 11:
        dv = "0"
    elif value == 10:
        dv = "K"
    else:
        dv = str(value)
    return f"{body}-{dv}"


def _make_numeric_rut(body: int) -> str:
    """Genera un RUT compatible con la matrícula, que solo admite dígitos."""

    rut = _make_rut(body)
    if not rut.endswith("-K"):
        return rut

    fallback_body = body + 4_000_000
    while True:
        rut = _make_rut(fallback_body)
        if not rut.endswith("-K"):
            return rut
        fallback_body += 1


def _make_student_identity(body: int, admission_year: int) -> StudentEnrollment:
    rut = _make_numeric_rut(body)
    rut_digits = rut.replace("-", "")
    return parse_student_enrollment(f"{rut_digits}{admission_year % 100:02d}")


DEMO_STUDENT_IDENTITIES = {
    STUDENT_DEMO_EMAIL: _make_student_identity(21000001, 2021),
    STUDENT_OTHER_EMAIL: _make_student_identity(21000010, 2022),
    STUDENT_ACTIVE_EMAIL: _make_student_identity(21000009, 2020),
}

DEMO_USERS = [
    {
        "email": STUDENT_DEMO_EMAIL,
        "rut": DEMO_STUDENT_IDENTITIES[STUDENT_DEMO_EMAIL].rut,
        "enrollment": DEMO_STUDENT_IDENTITIES[STUDENT_DEMO_EMAIL].value,
        "admission_year": DEMO_STUDENT_IDENTITIES[
            STUDENT_DEMO_EMAIL
        ].admission_year,
        "first_name": "Estudiante",
        "last_name": "Demo",
        "role": STUDENT_ROLE,
        "degree": "Ingenieria Civil Informatica",
        "cod_degree": "ICI",
    },
    {
        "email": STUDENT_OTHER_EMAIL,
        "rut": DEMO_STUDENT_IDENTITIES[STUDENT_OTHER_EMAIL].rut,
        "enrollment": DEMO_STUDENT_IDENTITIES[STUDENT_OTHER_EMAIL].value,
        "admission_year": DEMO_STUDENT_IDENTITIES[
            STUDENT_OTHER_EMAIL
        ].admission_year,
        "first_name": "Estudiante",
        "last_name": "Otro",
        "role": STUDENT_ROLE,
        "degree": "Ingenieria Civil Informatica",
        "cod_degree": "ICI",
    },
    {
        "email": STUDENT_ACTIVE_EMAIL,
        "rut": DEMO_STUDENT_IDENTITIES[STUDENT_ACTIVE_EMAIL].rut,
        "enrollment": DEMO_STUDENT_IDENTITIES[STUDENT_ACTIVE_EMAIL].value,
        "admission_year": DEMO_STUDENT_IDENTITIES[
            STUDENT_ACTIVE_EMAIL
        ].admission_year,
        "first_name": "Estudiante",
        "last_name": "Activo",
        "role": STUDENT_ROLE,
        "degree": "Ingenieria Civil Informatica",
        "cod_degree": "ICI",
    },
    {
        "email": "encargado.practicas@ufrontera.cl",
        "rut": "21000003-1",
        "first_name": "Encargado",
        "last_name": "Practicas",
        "role": PRACTICE_MANAGER_ROLE,
    },
    {
        "email": "director.carrera@ufrontera.cl",
        "rut": "21000004-1",
        "first_name": "Director",
        "last_name": "Carrera",
        "role": CAREER_DIRECTOR_ROLE,
    },
    {
        "email": "secretaria.carrera@ufrontera.cl",
        "rut": "21000005-1",
        "first_name": "Secretaria",
        "last_name": "Carrera",
        "role": SECRETARY_ROLE,
    },
    {
        "email": "supervisor.demo@empresa.cl",
        "rut": "21000006-1",
        "first_name": "Supervisor",
        "last_name": "Demo",
        "role": SUPERVISOR_ROLE,
    },
    {
        "email": "fica.reportes@ufrontera.cl",
        "rut": "21000007-1",
        "first_name": "FICA",
        "last_name": "Reportes",
        "role": FICA_ROLE,
    },
    {
        "email": DEFAULT_ADMIN_EMAIL,
        "rut": "21000008-1",
        "first_name": "Superadmin",
        "last_name": "Plataforma",
        "role": SUPERADMIN_ROLE,
    },
]

DEMO_EMAILS = [user["email"] for user in DEMO_USERS] + list(LEGACY_DEMO_EMAILS)
DEMO_ORG_PREFIX = "Demo QA"
REALISTIC_PRACTICE_REQUIREMENT_ORDER = (
    PracticeTypeEnum.practice_1,
    PracticeTypeEnum.practice_2,
    PracticeTypeEnum.controlled_practice,
    PracticeTypeEnum.thesis,
)
REALISTIC_FINAL_PRACTICE_OPTIONS = (
    PracticeTypeEnum.controlled_practice,
    PracticeTypeEnum.thesis,
)


@dataclass(frozen=True)
class SeedContext:
    users: dict[str, User]
    roles: dict[str, Role]
    states: dict[str, CurrentState]
    password_hash: str


@dataclass(frozen=True)
class RealisticPracticePlan:
    current_type: PracticeTypeEnum | None
    current_state_name: str | None
    completed_previous: tuple[PracticeTypeEnum, ...]
    enabled_type: PracticeTypeEnum | None = None
    next_after_completion: PracticeTypeEnum | None = None


def _build_realistic_practice_plan(index: int, active: bool) -> RealisticPracticePlan:
    """Define un avance demo que respeta el orden normal de prácticas."""

    if not active:
        inactive_history = (
            (),
            (PracticeTypeEnum.practice_1,),
            (PracticeTypeEnum.practice_1, PracticeTypeEnum.practice_2),
        )
        return RealisticPracticePlan(
            current_type=None,
            current_state_name=None,
            completed_previous=inactive_history[index % len(inactive_history)],
        )

    final_choice = (
        PracticeTypeEnum.controlled_practice
        if index % 2 == 0
        else PracticeTypeEnum.thesis
    )
    profiles = (
        RealisticPracticePlan(
            current_type=None,
            current_state_name=None,
            completed_previous=(),
            enabled_type=PracticeTypeEnum.practice_1,
        ),
        RealisticPracticePlan(
            PracticeTypeEnum.practice_1,
            "Pendiente",
            (),
        ),
        RealisticPracticePlan(
            PracticeTypeEnum.practice_1,
            "En revisión",
            (),
        ),
        RealisticPracticePlan(
            PracticeTypeEnum.practice_1,
            "Aprobada",
            (),
            next_after_completion=PracticeTypeEnum.practice_2,
        ),
        RealisticPracticePlan(
            PracticeTypeEnum.practice_1,
            "Rechazada",
            (),
        ),
        RealisticPracticePlan(
            PracticeTypeEnum.practice_2,
            "Pendiente",
            (PracticeTypeEnum.practice_1,),
        ),
        RealisticPracticePlan(
            PracticeTypeEnum.practice_2,
            "En revisión",
            (PracticeTypeEnum.practice_1,),
        ),
        RealisticPracticePlan(
            PracticeTypeEnum.practice_2,
            "Aprobada",
            (PracticeTypeEnum.practice_1,),
            next_after_completion=final_choice,
        ),
        RealisticPracticePlan(
            PracticeTypeEnum.practice_2,
            "Rechazada",
            (PracticeTypeEnum.practice_1,),
        ),
        RealisticPracticePlan(
            PracticeTypeEnum.controlled_practice,
            "Pendiente",
            (PracticeTypeEnum.practice_1, PracticeTypeEnum.practice_2),
        ),
        RealisticPracticePlan(
            PracticeTypeEnum.controlled_practice,
            "Aprobada",
            (PracticeTypeEnum.practice_1, PracticeTypeEnum.practice_2),
        ),
        RealisticPracticePlan(
            PracticeTypeEnum.controlled_practice,
            "Rechazada",
            (PracticeTypeEnum.practice_1, PracticeTypeEnum.practice_2),
        ),
        RealisticPracticePlan(
            PracticeTypeEnum.thesis,
            "Pendiente",
            (PracticeTypeEnum.practice_1, PracticeTypeEnum.practice_2),
        ),
        RealisticPracticePlan(
            PracticeTypeEnum.thesis,
            "En revisión",
            (PracticeTypeEnum.practice_1, PracticeTypeEnum.practice_2),
        ),
        RealisticPracticePlan(
            PracticeTypeEnum.thesis,
            "Aprobada",
            (PracticeTypeEnum.practice_1, PracticeTypeEnum.practice_2),
        ),
    )
    return profiles[(index - 1) % len(profiles)]


def _realistic_current_requirement_status(
    plan: RealisticPracticePlan,
    final_result: FinalResultEnum,
) -> str:
    if final_result == FinalResultEnum.passed:
        return "Aprobada"
    if plan.current_state_name == "Rechazada":
        return "Rechazada"
    if plan.current_state_name == "En revisión":
        return "En revisión"
    return "Habilitada"


def _build_realistic_requirement_statuses(
    plan: RealisticPracticePlan,
    final_result: FinalResultEnum,
) -> dict[PracticeTypeEnum, str]:
    statuses = {
        practice_type: "Pendiente"
        for practice_type in REALISTIC_PRACTICE_REQUIREMENT_ORDER
    }
    for practice_type in plan.completed_previous:
        statuses[practice_type] = "Aprobada"

    if plan.enabled_type is not None:
        statuses[plan.enabled_type] = "Habilitada"

    if plan.current_type is not None:
        statuses[plan.current_type] = _realistic_current_requirement_status(
            plan,
            final_result,
        )

    if (
        final_result == FinalResultEnum.passed
        and plan.next_after_completion is not None
        and statuses[plan.next_after_completion] == "Pendiente"
    ):
        statuses[plan.next_after_completion] = "Habilitada"

    return statuses


class DemoSeeder:
    def __init__(self, session: AsyncSession, password: str) -> None:
        self.session = session
        self.password_hash = PasswordService().hash_password(password)
        self.stats: Counter[str] = Counter()

    async def run(
        self,
        scenarios: set[str] | None = None,
        *,
        bulk_students: int = 0,
        realista: bool = False,
        realistic_students: int = DEFAULT_REALISTIC_STUDENT_COUNT,
    ) -> None:
        selected = set(DEFAULT_SCENARIOS if scenarios is None else scenarios)
        if "all" in selected:
            selected = set(DEFAULT_SCENARIOS)
        selected.discard("base")

        await self._ensure_role_enum_values()
        roles = await self._ensure_roles()
        states = await self._ensure_current_states()
        await self._ensure_document_types()

        needs_demo_users = bool(selected & DEFAULT_SCENARIOS) or realista
        users: dict[str, User] = {}
        if needs_demo_users:
            users = await self._ensure_users(roles)
        if bulk_students > 0:
            await self._ensure_bulk_students(roles, bulk_students)

        if not needs_demo_users:
            await self.session.commit()
            return

        context = SeedContext(
            users=users,
            roles=roles,
            states=states,
            password_hash=self.password_hash,
        )
        if "induction" in selected:
            await self._ensure_induction(context)
        if "requirements" in selected:
            await self._ensure_registration_requirements(context)
            await self._ensure_academic_requirements(context)
        if "internships" in selected:
            await self._ensure_internships(context)
        if "notifications" in selected:
            await self._ensure_notifications(context)
        if realista:
            await self._ensure_realistic_dataset(context, realistic_students)
        await self.session.commit()

    async def clean(self) -> None:
        users = await self._get_demo_users()
        user_ids = [user.id for user in users]

        internship_ids = await self._get_demo_internship_ids(user_ids)
        if user_ids:
            from app.modules.auth.models.account_activation_token_model import (
                AccountActivationToken,
            )
            from app.modules.auth.models.refresh_token_model import RefreshToken
            from app.modules.data_portability.models.data_portability_model import (
                DataPortabilityRequest,
            )
            from app.modules.presentation_letters.models.presentation_letter_model import (
                PresentationLetterTemplate,
            )
            from app.modules.scheduling.models.scheduling_config_model import (
                SchedulingConfig,
            )
            from app.modules.scheduling.models.scheduling_request_model import (
                SchedulingRequest,
            )
            from app.modules.self_evaluations.models.self_evaluation_model import (
                SelfEvaluation,
            )
            from app.modules.supervisor_evaluations.models.supervisor_evaluation_model import (
                SupervisorEvaluationInvitation,
            )

            await self.session.execute(
                update(InternshipStatusHistory)
                .where(InternshipStatusHistory.actor_id.in_(user_ids))
                .values(actor_id=None)
            )
            from app.modules.internships.models.internship_dirae_status_history_model import (
                InternshipDiraeStatusHistory,
            )

            await self.session.execute(
                update(InternshipDiraeStatusHistory)
                .where(InternshipDiraeStatusHistory.actor_id.in_(user_ids))
                .values(actor_id=None)
            )
            await self.session.execute(
                update(InternshipException)
                .where(InternshipException.authorized_by.in_(user_ids))
                .values(authorized_by=None)
            )
            await self.session.execute(
                update(Internship)
                .where(Internship.cancelled_by.in_(user_ids))
                .values(cancelled_by=None)
            )
            await self.session.execute(
                update(Internship)
                .where(Internship.insurance_validated_by.in_(user_ids))
                .values(insurance_validated_by=None)
            )
            await self.session.execute(
                update(Document)
                .where(Document.reviewed_by.in_(user_ids))
                .values(reviewed_by=None)
            )
            await self.session.execute(
                update(Document)
                .where(Document.deleted_by.in_(user_ids))
                .values(deleted_by=None)
            )
            await self.session.execute(
                update(StudentInternshipRequirement)
                .where(StudentInternshipRequirement.status_updated_by.in_(user_ids))
                .values(status_updated_by=None)
            )
            await self.session.execute(
                update(StudentRegistrationRequirement)
                .where(StudentRegistrationRequirement.updated_by.in_(user_ids))
                .values(updated_by=None)
            )
            await self.session.execute(
                update(SelfEvaluation)
                .where(SelfEvaluation.reopened_by.in_(user_ids))
                .values(reopened_by=None)
            )
            await self.session.execute(
                update(SupervisorEvaluationInvitation)
                .where(SupervisorEvaluationInvitation.created_by.in_(user_ids))
                .values(created_by=None)
            )
            await self.session.execute(
                update(SchedulingRequest)
                .where(SchedulingRequest.coordinator_id.in_(user_ids))
                .values(coordinator_id=None)
            )
            await self.session.execute(
                update(SchedulingRequest)
                .where(SchedulingRequest.target_coordinator_id.in_(user_ids))
                .values(target_coordinator_id=None)
            )
            await self.session.execute(
                update(PresentationLetterTemplate)
                .where(PresentationLetterTemplate.created_by.in_(user_ids))
                .values(created_by=None)
            )
            await self.session.execute(
                update(PresentationLetterTemplate)
                .where(PresentationLetterTemplate.updated_by.in_(user_ids))
                .values(updated_by=None)
            )
            await self.session.execute(
                update(AccountActivationToken)
                .where(AccountActivationToken.created_by_id.in_(user_ids))
                .values(created_by_id=None)
            )
            await self.session.execute(
                delete(RefreshToken).where(RefreshToken.user_id.in_(user_ids))
            )
            await self.session.execute(
                delete(AccountActivationToken).where(
                    AccountActivationToken.user_id.in_(user_ids)
                )
            )
            await self.session.execute(
                delete(DataPortabilityRequest).where(
                    DataPortabilityRequest.user_id.in_(user_ids)
                )
            )
            await self.session.execute(
                delete(SchedulingConfig).where(
                    SchedulingConfig.coordinator_id.in_(user_ids)
                )
            )

        if internship_ids:
            from app.modules.self_evaluations.models.self_evaluation_model import (
                SelfEvaluation,
            )
            from app.modules.supervisor_evaluations.models.supervisor_evaluation_model import (
                SupervisorEvaluation,
                SupervisorEvaluationInvitation,
            )
            from app.modules.scheduling.models.presentation_model import Presentation
            from app.modules.scheduling.models.scheduling_request_model import (
                SchedulingRequest,
            )

            await self.session.execute(
                delete(SelfEvaluation).where(
                    SelfEvaluation.internship_id.in_(internship_ids)
                )
            )
            await self.session.execute(
                delete(SupervisorEvaluation).where(
                    SupervisorEvaluation.internship_id.in_(internship_ids)
                )
            )
            await self.session.execute(
                delete(SupervisorEvaluationInvitation).where(
                    SupervisorEvaluationInvitation.internship_id.in_(internship_ids)
                )
            )
            await self.session.execute(
                delete(SchedulingRequest).where(
                    SchedulingRequest.internship_id.in_(internship_ids)
                )
            )
            await self.session.execute(
                delete(Presentation).where(
                    Presentation.internship_id.in_(internship_ids)
                )
            )
            await self.session.execute(
                delete(Document).where(Document.internship_id.in_(internship_ids))
            )
            await self.session.execute(
                delete(InternshipStatusHistory).where(
                    InternshipStatusHistory.internship_id.in_(internship_ids)
                )
            )
            await self.session.execute(
                delete(InternshipException).where(
                    InternshipException.internship_id.in_(internship_ids)
                )
            )
            await self.session.execute(
                delete(Internship).where(Internship.id.in_(internship_ids))
            )

        if user_ids:
            from app.modules.scheduling.models.presentation_model import Presentation
            from app.modules.scheduling.models.scheduling_request_model import (
                SchedulingRequest,
            )
            from app.modules.presentation_letters.models.presentation_letter_model import (
                PresentationLetter,
            )

            presentation_ids = select(Presentation.id).where(
                Presentation.user_id.in_(user_ids)
                | Presentation.owner_id.in_(user_ids)
            )
            document_ids = select(Document.id).where(Document.user_id.in_(user_ids))
            await self.session.execute(
                update(Presentation)
                .where(Presentation.document_id.in_(document_ids))
                .values(document_id=None)
                .execution_options(synchronize_session=False)
            )
            await self.session.execute(
                update(SchedulingRequest)
                .where(SchedulingRequest.presentation_id.in_(presentation_ids))
                .values(presentation_id=None)
                .execution_options(synchronize_session=False)
            )
            await self.session.execute(
                update(SchedulingRequest)
                .where(SchedulingRequest.document_id.in_(document_ids))
                .values(document_id=None)
                .execution_options(synchronize_session=False)
            )
            await self.session.execute(
                delete(SchedulingRequest).where(
                    SchedulingRequest.student_id.in_(user_ids)
                )
            )
            await self.session.execute(
                delete(Presentation).where(
                    Presentation.user_id.in_(user_ids)
                    | Presentation.owner_id.in_(user_ids)
                )
            )
            await self.session.execute(
                delete(PresentationLetter).where(
                    PresentationLetter.student_id.in_(user_ids)
                )
            )
            await self.session.execute(
                delete(SelfEvaluation).where(SelfEvaluation.student_id.in_(user_ids))
            )
            await self.session.execute(
                delete(Document).where(Document.user_id.in_(user_ids))
            )
            await self.session.execute(
                text("DELETE FROM logaction WHERE user_id = ANY(:user_ids)"),
                {"user_ids": user_ids},
            )
            await self.session.execute(
                delete(Notification).where(
                    Notification.recipient_user_id.in_(user_ids)
                )
            )
            await self.session.execute(
                delete(InductionAttempt).where(InductionAttempt.user_id.in_(user_ids))
            )
            await self.session.execute(
                delete(StudentRegistrationRequirement).where(
                    StudentRegistrationRequirement.user_id.in_(user_ids)
                )
            )
            await self.session.execute(
                delete(StudentInternshipRequirement).where(
                    StudentInternshipRequirement.user_id.in_(user_ids)
                )
            )
            await self.session.execute(
                delete(UserRole).where(UserRole.user_id.in_(user_ids))
            )
            await self.session.execute(delete(User).where(User.id.in_(user_ids)))

        await self._delete_demo_induction()
        await self.session.commit()
        self.stats["deleted"] += len(user_ids)

    async def _delete_demo_induction(self) -> None:
        result = await self.session.execute(
            select(InductionContentVersion).where(
                InductionContentVersion.title == DEMO_INDUCTION_TITLE
            )
        )
        contents = list(result.scalars().all())
        if not contents:
            return
        await self.session.execute(
            delete(InductionContentVersion).where(
                InductionContentVersion.id.in_([content.id for content in contents])
            )
        )
        self.stats["deleted"] += len(contents)

    async def reset_admin_only(
        self,
        *,
        admin_email: str,
        admin_password: str,
    ) -> None:
        await self._truncate_seeded_runtime_data()
        await self._ensure_role_enum_values()
        roles = await self._ensure_roles()
        await self._ensure_current_states()
        await self._ensure_document_types()
        admin = await self._get_user_by_email(admin_email)
        if admin is None:
            admin = User(
                email=admin_email,
                password_hash=self.password_hash,
                first_name="Superadmin",
                last_name="Plataforma",
                rut=_make_rut(29000000),
                sexo="No definido",
                is_active=True,
                is_verified=True,
                must_change_password=False,
            )
            self.session.add(admin)
            await self.session.flush()
            self.stats["created"] += 1
        else:
            admin.password_hash = PasswordService().hash_password(admin_password)
            admin.first_name = admin.first_name or "Superadmin"
            admin.last_name = admin.last_name or "Plataforma"
            admin.sexo = admin.sexo or "No definido"
            admin.is_active = True
            admin.is_verified = True
            admin.must_change_password = False
            self.stats["updated"] += 1

        await self._ensure_user_role(admin, roles[SUPERADMIN_ROLE])
        await self.session.flush()
        await self.session.execute(text("TRUNCATE TABLE logaction RESTART IDENTITY"))
        await self.session.commit()

    async def _truncate_seeded_runtime_data(self) -> None:
        await self.session.execute(
            text(
                """
                TRUNCATE TABLE
                    account_activation_tokens,
                    refresh_tokens,
                    notification,
                    supervisor_evaluations,
                    supervisor_evaluation_invitations,
                    self_evaluations,
                    data_portability_requests,
                    presentation_letter,
                    scheduling_config,
                    scheduling_request,
                    presentation,
                    document,
                    internship_status_history,
                    internship_dirae_status_history,
                    internship_exceptions,
                    internship,
                    induction_attempts,
                    induction_questions,
                    induction_videos,
                    induction_content_versions,
                    student_registration_requirements,
                    studentinternshiprequirement,
                    logaction,
                    user_roles,
                    users
                RESTART IDENTITY CASCADE
                """
            )
        )
        self.stats["deleted"] += 1

    async def _ensure_role_enum_values(self) -> None:
        for role_name in (FICA_ROLE, SUPERADMIN_ROLE):
            await self.session.execute(
                text(f"ALTER TYPE \"enumRole\" ADD VALUE IF NOT EXISTS '{role_name}'")
            )
        await self.session.commit()

    async def _ensure_roles(self) -> dict[str, Role]:
        roles: dict[str, Role] = {}
        for role_name in SYSTEM_ROLE_NAMES:
            role = await self._get_role(role_name)
            if role is None:
                role = Role(name=role_name, description=ROLE_DESCRIPTIONS[role_name])
                self.session.add(role)
                await self.session.flush()
                self.stats["created"] += 1
            elif role.description != ROLE_DESCRIPTIONS[role_name]:
                role.description = ROLE_DESCRIPTIONS[role_name]
                self.stats["updated"] += 1
            else:
                self.stats["reused"] += 1
            roles[role_name] = role
        return roles

    async def _ensure_current_states(self) -> dict[str, CurrentState]:
        states: dict[str, CurrentState] = {}
        for title, description in BASE_STATES:
            query = select(CurrentState).where(CurrentState.title == title)
            state = (await self.session.execute(query)).scalar_one_or_none()
            if state is None:
                state = CurrentState(title=title, description=description)
                self.session.add(state)
                await self.session.flush()
                self.stats["created"] += 1
            elif state.description != description:
                state.description = description
                self.stats["updated"] += 1
            else:
                self.stats["reused"] += 1
            states[title] = state
        return states

    async def _ensure_document_types(self) -> None:
        for name, description, is_required, category, is_sensitive in BASE_DOCUMENT_TYPES:
            query = select(DocumentType).where(DocumentType.name == name)
            document_type = (await self.session.execute(query)).scalar_one_or_none()
            if document_type is None:
                self.session.add(
                    DocumentType(
                        name=name,
                        description=description,
                        is_required=is_required,
                        category=category,
                        is_sensitive=is_sensitive,
                    )
                )
                await self.session.flush()
                self.stats["created"] += 1
                continue

            changed = False
            for field_name, next_value in (
                ("description", description),
                ("is_required", is_required),
                ("category", category),
                ("is_sensitive", is_sensitive),
            ):
                if getattr(document_type, field_name) != next_value:
                    setattr(document_type, field_name, next_value)
                    changed = True
            if not document_type.is_active:
                document_type.is_active = True
                changed = True
            self.stats["updated" if changed else "reused"] += 1

    async def _ensure_users(self, roles: dict[str, Role]) -> dict[str, User]:
        users: dict[str, User] = {}
        for data in DEMO_USERS:
            user = await self._get_user_by_email_or_rut(data["email"], data["rut"])
            if user is None:
                user = User(
                    email=data["email"],
                    password_hash=self.password_hash,
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    rut=data["rut"],
                    enrollment=data.get("enrollment"),
                    degree=data.get("degree"),
                    cod_degree=data.get("cod_degree"),
                    admission_year=data.get("admission_year"),
                    sexo="No definido",
                    is_active=True,
                    is_verified=True,
                )
                self.session.add(user)
                await self.session.flush()
                self.stats["created"] += 1
            else:
                changed = False
                field_names = [
                    "email",
                    "first_name",
                    "last_name",
                    "rut",
                    "degree",
                    "cod_degree",
                ]
                field_names.extend(
                    field_name
                    for field_name in ("enrollment", "admission_year")
                    if field_name in data
                )
                for field_name in field_names:
                    next_value = data.get(field_name)
                    if getattr(user, field_name) != next_value:
                        setattr(user, field_name, next_value)
                        changed = True
                if user.password_hash != self.password_hash:
                    user.password_hash = self.password_hash
                    changed = True
                if not user.is_active or not user.is_verified:
                    user.is_active = True
                    user.is_verified = True
                    changed = True
                self.stats["updated" if changed else "reused"] += 1

            await self._ensure_user_role(user, roles[data["role"]])
            users[data["email"]] = user
        return users

    async def _ensure_bulk_students(self, roles: dict[str, Role], count: int) -> None:
        if count < 0:
            raise ValueError("--bulk-students must be zero or greater")
        student_role = roles[STUDENT_ROLE]
        for index in range(1, count + 1):
            email = f"{BULK_STUDENT_EMAIL_PREFIX}{index:04d}@ufromail.cl"
            identity = _make_student_identity(22000000 + index, 2022)
            user = await self._get_user_by_email_or_rut(email, identity.rut)
            if user is None:
                user = User(
                    email=email,
                    password_hash=self.password_hash,
                    first_name="Estudiante",
                    last_name=f"QA {index:04d}",
                    rut=identity.rut,
                    enrollment=identity.value,
                    degree="Ingenieria Civil Informatica",
                    cod_degree="ICI",
                    admission_year=identity.admission_year,
                    sexo="No definido",
                    is_active=True,
                    is_verified=True,
                )
                self.session.add(user)
                await self.session.flush()
                self.stats["created"] += 1
            else:
                changed = False
                for field_name, next_value in (
                    ("email", email),
                    ("first_name", "Estudiante"),
                    ("last_name", f"QA {index:04d}"),
                    ("rut", identity.rut),
                    ("enrollment", identity.value),
                    ("degree", "Ingenieria Civil Informatica"),
                    ("cod_degree", "ICI"),
                    ("admission_year", identity.admission_year),
                    ("sexo", "No definido"),
                ):
                    if getattr(user, field_name) != next_value:
                        setattr(user, field_name, next_value)
                        changed = True
                if not user.is_active or not user.is_verified:
                    user.is_active = True
                    user.is_verified = True
                    changed = True
                self.stats["updated" if changed else "reused"] += 1
            await self._ensure_user_role(user, student_role)

    async def _ensure_realistic_dataset(
        self,
        context: SeedContext,
        count: int,
    ) -> None:
        if count < 20:
            raise ValueError("--realistic-students must be at least 20")

        today = date.today()
        periods = (
            PracticePeriodEnum.semester,
            PracticePeriodEnum.summer,
            PracticePeriodEnum.winter,
        )

        for index in range(1, count + 1):
            user = await self._ensure_realistic_student(
                context.roles[STUDENT_ROLE],
                index,
            )
            plan = _build_realistic_practice_plan(index, bool(user.is_active))
            if plan.current_state_name is None:
                completion_status = CompletionStatusEnum.not_started
                final_result = FinalResultEnum.pending
            else:
                completion_status, final_result = self._realistic_completion(
                    index,
                    plan.current_state_name,
                )
            await self._ensure_realistic_requirements(
                user,
                index,
                plan,
                final_result,
            )

            for previous_type in plan.completed_previous:
                await self._ensure_completed_previous_level(
                    context,
                    user,
                    previous_type,
                    index,
                    today,
                )

            if plan.current_type is None or plan.current_state_name is None:
                continue

            status = context.states[plan.current_state_name]
            start_date = today - timedelta(days=45 + (index % 90))
            end_date = (
                today - timedelta(days=index % 30)
                if completion_status == CompletionStatusEnum.finalized
                else today + timedelta(days=15 + (index % 75))
            )
            internship = await self._ensure_internship(
                owner=user,
                status=status,
                org_name=f"Realista QA {index:04d} {plan.current_type.value}",
                internship_type=plan.current_type,
                period=periods[index % len(periods)],
                has_school_insurance=index % 5 != 0,
                with_documents=plan.current_state_name == "Aprobada" and index % 3 != 0,
                start_date=start_date,
                end_date=end_date,
                completion_status=completion_status,
                final_result=final_result,
                blocks_new_registration=(
                    plan.current_state_name != "Rechazada"
                    and final_result != FinalResultEnum.failed
                ),
            )
            if completion_status in {
                CompletionStatusEnum.pending_evaluations,
                CompletionStatusEnum.pending_presentation,
                CompletionStatusEnum.finalized,
            }:
                await self._ensure_self_evaluation(internship, user)
            if completion_status in {
                CompletionStatusEnum.pending_presentation,
                CompletionStatusEnum.finalized,
            }:
                await self._ensure_supervisor_evaluation(internship)

    async def _ensure_realistic_student(self, student_role: Role, index: int) -> User:
        current_year = date.today().year
        active = index % 7 != 0
        admission_year = (
            current_year - (index % 3)
            if active
            else current_year - (3 + (index % 5))
        )
        email = f"{REALISTIC_STUDENT_EMAIL_PREFIX}{index:04d}@ufromail.cl"
        identity = _make_student_identity(23000000 + index, admission_year)
        user = await self._get_user_by_email_or_rut(email, identity.rut)
        if user is None:
            user = User(
                email=email,
                password_hash=self.password_hash,
                first_name="Estudiante",
                last_name=f"Realista {index:04d}",
                rut=identity.rut,
                enrollment=identity.value,
                degree="Ingenieria Civil Informatica",
                cod_degree="ICI",
                admission_year=identity.admission_year,
                sexo="No definido",
                is_active=active,
                is_verified=active,
                must_change_password=False,
            )
            self.session.add(user)
            await self.session.flush()
            self.stats["created"] += 1
        else:
            changed = False
            for field_name, next_value in (
                ("email", email),
                ("first_name", "Estudiante"),
                ("last_name", f"Realista {index:04d}"),
                ("rut", identity.rut),
                ("enrollment", identity.value),
                ("degree", "Ingenieria Civil Informatica"),
                ("cod_degree", "ICI"),
                ("admission_year", identity.admission_year),
                ("sexo", "No definido"),
                ("is_active", active),
                ("is_verified", active),
                ("must_change_password", False),
            ):
                if getattr(user, field_name) != next_value:
                    setattr(user, field_name, next_value)
                    changed = True
            self.stats["updated" if changed else "reused"] += 1

        await self._ensure_user_role(user, student_role)
        return user

    async def _ensure_realistic_requirements(
        self,
        user: User,
        index: int,
        plan: RealisticPracticePlan,
        final_result: FinalResultEnum,
    ) -> None:
        active = bool(user.is_active)
        await self._ensure_requirement(
            user,
            RegistrationRequirementType.INDUCTION,
            active and index % 4 != 0,
        )
        await self._ensure_requirement(
            user,
            RegistrationRequirementType.SCHOOL_INSURANCE,
            active and index % 5 != 0,
        )

        requirement_statuses = _build_realistic_requirement_statuses(
            plan,
            final_result,
        )
        for practice_type in REALISTIC_PRACTICE_REQUIREMENT_ORDER:
            await self._ensure_academic_requirement(
                user,
                practice_type.value,
                requirement_statuses[practice_type],
            )

    @staticmethod
    def _realistic_completion(
        index: int,
        status_name: str,
    ) -> tuple[CompletionStatusEnum, FinalResultEnum]:
        if status_name != "Aprobada":
            return CompletionStatusEnum.not_started, FinalResultEnum.pending
        variants = (
            (CompletionStatusEnum.in_progress, FinalResultEnum.pending),
            (CompletionStatusEnum.pending_evaluations, FinalResultEnum.pending),
            (CompletionStatusEnum.pending_presentation, FinalResultEnum.pending),
            (CompletionStatusEnum.finalized, FinalResultEnum.passed),
            (CompletionStatusEnum.finalized, FinalResultEnum.failed),
        )
        return variants[index % len(variants)]

    async def _ensure_completed_previous_level(
        self,
        context: SeedContext,
        user: User,
        practice_type: PracticeTypeEnum,
        index: int,
        today: date,
    ) -> None:
        if practice_type == PracticeTypeEnum.practice_1:
            start_offset = 420 + (index % 45)
            end_offset = 330 + (index % 35)
        elif practice_type == PracticeTypeEnum.practice_2:
            start_offset = 260 + (index % 45)
            end_offset = 170 + (index % 35)
        else:
            start_offset = 180 + (index % 30)
            end_offset = 95 + (index % 25)

        internship = await self._ensure_internship(
            owner=user,
            status=context.states["Aprobada"],
            org_name=f"Realista QA historial {index:04d} {practice_type.value}",
            internship_type=practice_type,
            period=PracticePeriodEnum.semester,
            has_school_insurance=True,
            with_documents=True,
            start_date=today - timedelta(days=start_offset),
            end_date=today - timedelta(days=end_offset),
            completion_status=CompletionStatusEnum.finalized,
            final_result=FinalResultEnum.passed,
            blocks_new_registration=False,
        )
        await self._ensure_self_evaluation(internship, user)
        await self._ensure_supervisor_evaluation(internship)

    async def _ensure_user_role(self, user: User, role: Role) -> None:
        query = select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
        existing = (await self.session.execute(query)).scalar_one_or_none()
        if existing is None:
            self.session.add(UserRole(user_id=user.id, role_id=role.id))
            await self.session.flush()
            self.stats["created"] += 1
        else:
            self.stats["reused"] += 1

    async def _get_states(self) -> dict[str, CurrentState]:
        result = await self.session.execute(select(CurrentState))
        return {state.title: state for state in result.scalars().all()}

    async def _ensure_induction(self, context: SeedContext) -> None:
        await self._deactivate_other_active_inductions()
        query = select(InductionContentVersion).where(
            InductionContentVersion.title == DEMO_INDUCTION_TITLE
        )
        content = (await self.session.execute(query)).scalar_one_or_none()
        if content is None:
            content = InductionContentVersion(
                title=DEMO_INDUCTION_TITLE,
                description="Version publicada para escenarios demo de QA.",
                status=ContentStatusEnum.published,
                is_active=True,
                min_score=1,
                published_at=datetime.now(UTC).replace(tzinfo=None),
            )
            self.session.add(content)
            await self.session.flush()
            self.session.add(
                InductionVideo(
                    content_version_id=content.id,
                    title="Video demo QA",
                    video_url="https://example.com/induccion-demo-qa",
                    order=1,
                )
            )
            question = InductionQuestion(
                content_version_id=content.id,
                question_text="Confirma que revisaste la induccion demo.",
                options=INDUCTION_OPTIONS,
                correct_answer=INDUCTION_CORRECT_ANSWER,
                order=1,
            )
            self.session.add(question)
            await self.session.flush()
            self.stats["created"] += 1
        else:
            content.status = ContentStatusEnum.published
            content.is_active = True
            content.min_score = 1
            self.stats["reused"] += 1

        question = await self._ensure_demo_induction_question(content)

        await self._ensure_induction_attempt(
            user=context.users[STUDENT_DEMO_EMAIL],
            content=content,
            question=question,
            passed=True,
        )

    async def _deactivate_other_active_inductions(self) -> None:
        result = await self.session.execute(
            select(InductionContentVersion).where(
                InductionContentVersion.is_active.is_(True),
                InductionContentVersion.title != DEMO_INDUCTION_TITLE,
            )
        )
        versions = list(result.scalars().all())
        for version in versions:
            version.is_active = False

        if versions:
            self.stats["updated"] += len(versions)

    async def _ensure_demo_induction_question(
        self,
        content: InductionContentVersion,
    ) -> InductionQuestion:
        query = select(InductionQuestion).where(
            InductionQuestion.content_version_id == content.id,
            InductionQuestion.order == 1,
        )
        question = (await self.session.execute(query)).scalar_one_or_none()
        if question is None:
            question = InductionQuestion(
                content_version_id=content.id,
                question_text="Confirma que revisaste la induccion demo.",
                options=INDUCTION_OPTIONS,
                correct_answer=INDUCTION_CORRECT_ANSWER,
                order=1,
            )
            self.session.add(question)
            await self.session.flush()
            self.stats["created"] += 1
            return question

        changed = False
        if question.options != INDUCTION_OPTIONS:
            question.options = INDUCTION_OPTIONS
            changed = True
        if question.correct_answer != INDUCTION_CORRECT_ANSWER:
            question.correct_answer = INDUCTION_CORRECT_ANSWER
            changed = True
        if changed:
            self.stats["updated"] += 1
        else:
            self.stats["reused"] += 1

        return question

    async def _ensure_induction_attempt(
        self,
        *,
        user: User,
        content: InductionContentVersion,
        question: InductionQuestion,
        passed: bool,
    ) -> None:
        answers = {str(question.id): INDUCTION_CORRECT_ANSWER}
        query = select(InductionAttempt).where(
            InductionAttempt.user_id == user.id,
            InductionAttempt.content_version_id == content.id,
        )
        attempt = (await self.session.execute(query)).scalar_one_or_none()
        if attempt is None:
            self.session.add(
                InductionAttempt(
                    user_id=user.id,
                    content_version_id=content.id,
                    answers=answers,
                    score=1 if passed else 0,
                    passed=passed,
                )
            )
            self.stats["created"] += 1
        elif attempt.answers != answers or attempt.passed != passed:
            attempt.answers = answers
            attempt.score = 1 if passed else 0
            attempt.passed = passed
            self.stats["updated"] += 1
        else:
            self.stats["reused"] += 1

    async def _ensure_registration_requirements(self, context: SeedContext) -> None:
        await self._ensure_requirement(
            context.users[STUDENT_DEMO_EMAIL],
            RegistrationRequirementType.INDUCTION,
            True,
        )
        await self._ensure_requirement(
            context.users[STUDENT_DEMO_EMAIL],
            RegistrationRequirementType.SCHOOL_INSURANCE,
            True,
        )
        await self._ensure_requirement(
            context.users[STUDENT_OTHER_EMAIL],
            RegistrationRequirementType.INDUCTION,
            False,
        )
        await self._ensure_requirement(
            context.users[STUDENT_OTHER_EMAIL],
            RegistrationRequirementType.SCHOOL_INSURANCE,
            False,
        )

    async def _ensure_requirement(
        self,
        user: User,
        requirement: RegistrationRequirementType,
        completed: bool,
    ) -> None:
        query = select(StudentRegistrationRequirement).where(
            StudentRegistrationRequirement.user_id == user.id,
            StudentRegistrationRequirement.requirement == requirement,
        )
        item = (await self.session.execute(query)).scalar_one_or_none()
        completed_at = datetime.now(UTC).replace(tzinfo=None) if completed else None
        if item is None:
            self.session.add(
                StudentRegistrationRequirement(
                    user_id=user.id,
                    requirement=requirement,
                    is_completed=completed,
                    completed_at=completed_at,
                )
            )
            self.stats["created"] += 1
        elif item.is_completed != completed:
            item.is_completed = completed
            item.completed_at = completed_at
            self.stats["updated"] += 1
        else:
            self.stats["reused"] += 1

    async def _ensure_academic_requirements(self, context: SeedContext) -> None:
        for email, requirements in DEMO_ACADEMIC_REQUIREMENTS.items():
            user = context.users[email]
            for practice_type, status in requirements.items():
                await self._ensure_academic_requirement(user, practice_type, status)

    async def _ensure_academic_requirement(
        self,
        user: User,
        practice_type: str,
        status: str,
    ) -> None:
        query = select(StudentInternshipRequirement).where(
            StudentInternshipRequirement.user_id == user.id,
            StudentInternshipRequirement.type == practice_type,
        )
        item = (await self.session.execute(query)).scalar_one_or_none()
        now = datetime.now(UTC).replace(tzinfo=None)

        if item is None:
            self.session.add(
                StudentInternshipRequirement(
                    user_id=user.id,
                    type=practice_type,
                    status=status,
                    status_updated_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
            self.stats["created"] += 1
        elif item.status != status:
            item.status = status
            item.status_updated_at = now
            item.updated_at = now
            self.stats["updated"] += 1
        else:
            self.stats["reused"] += 1

    async def _ensure_internships(self, context: SeedContext) -> None:
        pending = context.states["Pendiente"]
        approved = context.states["Aprobada"]
        internship = await self._ensure_internship(
            owner=context.users[STUDENT_DEMO_EMAIL],
            status=approved,
            org_name=f"{DEMO_ORG_PREFIX} exportable",
            internship_type=PracticeTypeEnum.practice_1,
            period=PracticePeriodEnum.semester,
            has_school_insurance=True,
            with_documents=True,
            start_date=date.today() - timedelta(days=70),
            end_date=date.today() - timedelta(days=10),
            completion_status=CompletionStatusEnum.pending_presentation,
            final_result=FinalResultEnum.pending,
        )
        await self._ensure_self_evaluation(internship, context.users[STUDENT_DEMO_EMAIL])
        await self._ensure_supervisor_evaluation(internship)

        blocked = await self._ensure_internship(
            owner=context.users[STUDENT_OTHER_EMAIL],
            status=pending,
            org_name=f"{DEMO_ORG_PREFIX} induccion pendiente",
            internship_type=PracticeTypeEnum.practice_1,
            period=PracticePeriodEnum.semester,
            has_school_insurance=False,
            with_documents=False,
        )
        await self._ensure_exception(
            internship=blocked,
            actor=context.users["encargado.practicas@ufrontera.cl"],
        )

        self.stats["skipped"] += len(UNSUPPORTED_DEMO_SCENARIOS)

    async def _ensure_self_evaluation(self, internship: Internship, student: User) -> None:
        from app.modules.self_evaluations.models.self_evaluation_model import (
            SelfEvaluation,
            SelfEvaluationStatusEnum,
        )
        from app.modules.self_evaluations.schemas.self_evaluation_schema import (
            SELF_EVALUATION_CRITERIA,
        )

        query = select(SelfEvaluation).where(
            SelfEvaluation.internship_id == internship.id,
            SelfEvaluation.student_id == student.id,
        )
        existing = (await self.session.execute(query)).scalar_one_or_none()

        responses = {
            "communication": 5,
            "teamwork": 5,
            "organization_understanding": 5,
            "process_understanding": 5,
            "risk_prevention": 5,
            "ethics": 5,
            "learning_application": 5,
        }

        if existing is None:
            self.session.add(
                SelfEvaluation(
                    internship_id=internship.id,
                    student_id=student.id,
                    form_version="1.0",
                    criteria_snapshot=SELF_EVALUATION_CRITERIA,
                    responses=responses,
                    observations="Autoevaluación de prueba completada.",
                    status=SelfEvaluationStatusEnum.submitted,
                    submitted_at=datetime.now(UTC).replace(tzinfo=None),
                )
            )
            self.stats["created"] += 1
        else:
            existing.responses = responses
            existing.status = SelfEvaluationStatusEnum.submitted
            self.stats["reused"] += 1

    async def _ensure_supervisor_evaluation(self, internship: Internship) -> None:
        from app.modules.supervisor_evaluations.models.supervisor_evaluation_model import (
            SupervisorEvaluation,
            SupervisorEvaluationInvitation,
        )

        # Primero asegurar que exista la invitación para que no se vea como bloqueada en el timeline
        inv_query = select(SupervisorEvaluationInvitation).where(
            SupervisorEvaluationInvitation.internship_id == internship.id
        )
        invitation = (await self.session.execute(inv_query)).scalar_one_or_none()
        now = datetime.now(UTC).replace(tzinfo=None)
        if invitation is None:
            import uuid
            token = str(uuid.uuid4())
            invitation = SupervisorEvaluationInvitation(
                internship_id=internship.id,
                supervisor_name_snapshot=internship.supervisor_name,
                supervisor_email_snapshot=internship.supervisor_email,
                token_hash=token,
                expires_at=now + timedelta(days=30),
                sent_at=now - timedelta(days=2),
                used_at=now - timedelta(days=1),
                created_at=now - timedelta(days=2),
            )
            self.session.add(invitation)
            await self.session.flush()
            self.stats["created"] += 1
        else:
            self.stats["reused"] += 1

        query = select(SupervisorEvaluation).where(
            SupervisorEvaluation.internship_id == internship.id
        )
        existing = (await self.session.execute(query)).scalar_one_or_none()

        criteria_scores = {
            "technical_performance": 5,
            "responsibility": 5,
            "communication": 5,
            "teamwork": 5,
            "autonomy": 5,
        }

        if existing is None:
            self.session.add(
                SupervisorEvaluation(
                    internship_id=internship.id,
                    invitation_id=invitation.id,
                    supervisor_name_snapshot=internship.supervisor_name,
                    supervisor_email_snapshot=internship.supervisor_email,
                    criteria_scores=criteria_scores,
                    observations="Excelente desempeño general durante su práctica.",
                    recommendation="recommended",
                    status="submitted",
                    submitted_at=now - timedelta(days=1),
                )
            )
            self.stats["created"] += 1
        else:
            existing.invitation_id = invitation.id
            existing.criteria_scores = criteria_scores
            existing.recommendation = "recommended"
            existing.status = "submitted"
            self.stats["reused"] += 1

    async def _ensure_internship(
        self,
        *,
        owner: User,
        status: CurrentState,
        org_name: str,
        internship_type: PracticeTypeEnum,
        period: PracticePeriodEnum,
        has_school_insurance: bool,
        with_documents: bool,
        start_date: date | None = None,
        end_date: date | None = None,
        completion_status: CompletionStatusEnum = CompletionStatusEnum.not_started,
        final_result: FinalResultEnum = FinalResultEnum.pending,
        blocks_new_registration: bool = True,
    ) -> Internship:
        query = select(Internship).where(
            Internship.user_id == owner.id,
            Internship.org_name == org_name,
        )
        internship = (await self.session.execute(query)).scalar_one_or_none()
        if internship is None:
            internship = Internship(
                org_name=org_name,
                sector="Tecnologia",
                address="Av. Demo 123",
                city="Temuco",
                org_phone="+56911111111",
                web="https://example.com",
                supervisor_name="Supervisor Demo",
                supervisor_profession="Ingeniero",
                supervisor_position="Jefe de Proyecto",
                supervisor_department="TI",
                supervisor_email="supervisor.demo@empresa.cl",
                supervisor_phone="+56922222222",
                start_date=start_date or date.today(),
                end_date=end_date or (date.today() + timedelta(days=60)),
                schedule="Lunes a viernes 09:00-18:00",
                days="Lunes,Martes,Miercoles,Jueves,Viernes",
                modality="Presencial",
                internship_address="Av. Demo 123",
                act_description="Actividades demo para QA",
                ben_description="Beneficio demo para QA",
                amount=0,
                status_id=status.id,
                user_id=owner.id,
                internship_period=period,
                internship_type=internship_type,
                has_school_insurance=has_school_insurance,
                blocks_new_registration=blocks_new_registration,
                insurance_status=(
                    SchoolInsuranceStatusEnum.validated
                    if has_school_insurance
                    else SchoolInsuranceStatusEnum.pending
                ),
                completion_status=completion_status,
                final_result=final_result,
            )
            self.session.add(internship)
            await self.session.flush()
            self.stats["created"] += 1
        else:
            internship.status_id = status.id
            internship.internship_period = period
            internship.internship_type = internship_type
            internship.has_school_insurance = has_school_insurance
            internship.blocks_new_registration = blocks_new_registration
            internship.insurance_status = (
                SchoolInsuranceStatusEnum.validated
                if has_school_insurance
                else SchoolInsuranceStatusEnum.pending
            )
            internship.start_date = start_date or date.today()
            internship.end_date = end_date or (date.today() + timedelta(days=60))
            internship.completion_status = completion_status
            internship.final_result = final_result
            self.stats["updated"] += 1

        if with_documents:
            await self._ensure_approved_required_documents(internship, owner)
        return internship

    async def _ensure_approved_required_documents(self, internship: Internship, owner: User) -> None:
        result = await self.session.execute(
            select(DocumentType).where(DocumentType.is_required.is_(True))
        )
        for document_type in result.scalars().all():
            query = select(Document).where(
                Document.internship_id == internship.id,
                Document.type_id == document_type.id,
                Document.file_name == f"demo-{document_type.id}.pdf",
            )
            document = (await self.session.execute(query)).scalar_one_or_none()
            if document is None:
                self.session.add(
                    Document(
                        file_name=f"demo-{document_type.id}.pdf",
                        file_path=f"demo/{internship.id}/demo-{document_type.id}.pdf",
                        extension="pdf",
                        status="approved",
                        size_bytes=128,
                        internship_id=internship.id,
                        type_id=document_type.id,
                        user_id=owner.id,
                        reviewed_at=datetime.now(UTC).replace(tzinfo=None),
                        reviewed_by=owner.id,
                    )
                )
                self.stats["created"] += 1
            else:
                self.stats["reused"] += 1

    async def _ensure_exception(self, internship: Internship, actor: User) -> None:
        query = select(InternshipException).where(
            InternshipException.internship_id == internship.id,
            InternshipException.rule == ExceptableRule.SCHOOL_INSURANCE,
        )
        exception = (await self.session.execute(query)).scalar_one_or_none()
        if exception is None:
            self.session.add(
                InternshipException(
                    internship_id=internship.id,
                    rule=ExceptableRule.SCHOOL_INSURANCE,
                    reason="Excepcion demo para validar flujo QA.",
                    authorized_by=actor.id,
                )
            )
            self.stats["created"] += 1
        else:
            self.stats["reused"] += 1
        internship.insurance_status = SchoolInsuranceStatusEnum.exception_authorized
        internship.insurance_validated_by = actor.id
        internship.insurance_validated_at = datetime.now(UTC).replace(tzinfo=None)
        internship.insurance_notes = "Excepcion demo para validar flujo QA."

    async def _ensure_notifications(self, context: SeedContext) -> None:
        recipient = context.users["encargado.practicas@ufrontera.cl"]
        for subject, event_type in (
            ("Demo notificacion no leida", NotificationEventTypeEnum.custom),
            ("Demo documento observado", NotificationEventTypeEnum.requirement_status_changed),
        ):
            await self._ensure_notification(
                recipient=recipient,
                subject=subject,
                content="Notificacion demo generada por seed_demo.py",
                event_type=event_type,
            )

        await self._ensure_notification(
            recipient=context.users[STUDENT_DEMO_EMAIL],
            subject=LONG_DEMO_NOTIFICATION_SUBJECT,
            content=LONG_DEMO_NOTIFICATION_CONTENT,
            event_type=NotificationEventTypeEnum.custom,
        )

    async def _ensure_notification(
        self,
        *,
        recipient: User,
        subject: str,
        content: str,
        event_type: NotificationEventTypeEnum,
    ) -> None:
        query = select(Notification).where(
            Notification.recipient_user_id == recipient.id,
            Notification.subject == subject,
        )
        notification = (await self.session.execute(query)).scalar_one_or_none()
        if notification is None:
            self.session.add(
                Notification(
                    recipient_user_id=recipient.id,
                    recipient_email=recipient.email,
                    event_type=event_type,
                    subject=subject,
                    content=content,
                    status=NotificationStatusEnum.simulated,
                    payload={"demo_seed": True},
                )
            )
            self.stats["created"] += 1
        else:
            notification.content = content
            notification.event_type = event_type
            self.stats["updated"] += 1

    async def _get_role(self, name: str) -> Role | None:
        return (await self.session.execute(select(Role).where(Role.name == name))).scalar_one_or_none()

    async def _get_user_by_email(self, email: str) -> User | None:
        return (await self.session.execute(select(User).where(User.email == email))).scalar_one_or_none()

    async def _get_user_by_email_or_rut(self, email: str, rut: str) -> User | None:
        return (
            await self.session.execute(
                select(User).where((User.email == email) | (User.rut == rut))
            )
        ).scalar_one_or_none()

    async def _get_demo_users(self) -> list[User]:
        result = await self.session.execute(
            select(User).where(
                or_(
                    User.email.in_(DEMO_EMAILS),
                    User.email.like(f"{BULK_STUDENT_EMAIL_PREFIX}%@ufromail.cl"),
                    User.email.like(f"{REALISTIC_STUDENT_EMAIL_PREFIX}%@ufromail.cl"),
                )
            )
        )
        return list(result.scalars().all())

    async def _get_demo_internship_ids(self, user_ids: list[int]) -> list[int]:
        if not user_ids:
            return []
        result = await self.session.execute(
            select(Internship.id).where(
                Internship.user_id.in_(user_ids),
            )
        )
        return list(result.scalars().all())

    def print_summary(self) -> None:
        for key in ("created", "updated", "reused", "skipped", "deleted"):
            if self.stats[key]:
                print(f"{key}: {self.stats[key]}")


def _ensure_not_production() -> None:
    env_names = ("ENVIRONMENT", "APP_ENV", "ENV", "MODE")
    active_values = {name: os.getenv(name, "").lower() for name in env_names}
    if any(value in {"prod", "production"} for value in active_values.values()):
        raise RuntimeError("seed_demo.py is disabled in production environments")


def _get_demo_password(explicit_password: str | None = None) -> str:
    password = explicit_password or os.getenv("DEMO_SEED_PASSWORD")
    if not password:
        raise RuntimeError("DEMO_SEED_PASSWORD is required")
    if len(password) < 8:
        raise RuntimeError("DEMO_SEED_PASSWORD must contain at least 8 characters")
    return password


def _generate_password() -> str:
    return secrets.token_urlsafe(18)


def _parse_scenarios(raw_values: list[str] | None) -> set[str] | None:
    if not raw_values:
        return None
    selected = set(raw_values)
    unknown = selected - VALID_SCENARIOS
    if unknown:
        raise RuntimeError(f"Unknown seed scenario(s): {', '.join(sorted(unknown))}")
    if "all" in selected:
        return set(DEFAULT_SCENARIOS)
    return selected


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo QA data")
    parser.add_argument("--clean", action="store_true", help="Remove demo data created by this script")
    parser.add_argument(
        "--only",
        action="append",
        choices=sorted(VALID_SCENARIOS),
        help=(
            "Seed only a scenario. Can be repeated. Options: base, users, "
            "induction, requirements, internships, notifications, all."
        ),
    )
    parser.add_argument(
        "--bulk-students",
        type=int,
        default=0,
        help="Create N additional QA student users for pagination/load checks",
    )
    parser.add_argument(
        "--realista",
        action="store_true",
        help="Seed a larger realistic QA dataset with active/inactive students and varied internship states",
    )
    parser.add_argument(
        "--realistic-students",
        type=int,
        default=DEFAULT_REALISTIC_STUDENT_COUNT,
        help="Number of students created by --realista",
    )
    parser.add_argument(
        "--reset-admin-only",
        action="store_true",
        help="Delete runtime/seeded data and leave only one active Superadmin user",
    )
    parser.add_argument(
        "--admin-email",
        default=DEFAULT_ADMIN_EMAIL,
        help="Email used by --reset-admin-only",
    )
    parser.add_argument(
        "--admin-password",
        help="Optional password for --reset-admin-only. If omitted, a random one is printed.",
    )
    parser.add_argument(
        "--password",
        help="Password for normal demo users. Defaults to DEMO_SEED_PASSWORD.",
    )
    args = parser.parse_args()

    _ensure_not_production()
    if args.clean and args.reset_admin_only:
        raise RuntimeError("--clean and --reset-admin-only cannot be used together")
    if args.clean and (args.only or args.bulk_students or args.realista):
        raise RuntimeError("--clean cannot be combined with --only, --bulk-students or --realista")
    if not args.realista and args.realistic_students != DEFAULT_REALISTIC_STUDENT_COUNT:
        raise RuntimeError("--realistic-students can only be used with --realista")

    scenarios = _parse_scenarios(args.only)
    needs_demo_password = (
        not args.clean
        and not args.reset_admin_only
        and (
            scenarios is None
            or bool(scenarios & DEFAULT_SCENARIOS)
            or args.bulk_students > 0
            or args.realista
        )
    )

    async with SessionLocal() as session:
        admin_password = args.admin_password or _generate_password()
        if args.reset_admin_only:
            password = admin_password
        elif needs_demo_password:
            password = _get_demo_password(args.password)
        else:
            password = args.password or os.getenv("DEMO_SEED_PASSWORD") or _generate_password()
        seeder = DemoSeeder(session, password)
        if args.clean:
            await seeder.clean()
        elif args.reset_admin_only:
            await seeder.reset_admin_only(
                admin_email=args.admin_email,
                admin_password=admin_password,
            )
            print("admin_email:", args.admin_email)
            print("admin_password:", admin_password)
        else:
            await seeder.run(
                scenarios,
                bulk_students=args.bulk_students,
                realista=args.realista,
                realistic_students=args.realistic_students,
            )
        seeder.print_summary()


if __name__ == "__main__":
    asyncio.run(_main())
