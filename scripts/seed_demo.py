"""Siembra datos demo idempotentes para QA local.

Uso local/Docker:
    DEMO_SEED_PASSWORD=demo-password uv run python scripts/seed_demo.py
    DEMO_SEED_PASSWORD=demo-password uv run python scripts/seed_demo.py --clean
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.database import SessionLocal
from app.modules.auth.models.role_model import Role
from app.modules.auth.models.user_model import User
from app.modules.auth.models.user_role_model import UserRole
from app.modules.auth.services.password_service import PasswordService
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
    Internship,
    PracticePeriodEnum,
    PracticeTypeEnum,
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
LEGACY_DEMO_EMAILS = ("estudiante.demo@correo.cl", "estudiante.otro@correo.cl")
INDUCTION_OPTIONS = {"accept": "Entiendo y acepto", "reject": "No acepto"}
INDUCTION_CORRECT_ANSWER = "accept"
DEMO_INDUCTION_TITLE = "Induccion demo QA publicada"
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
    "agenda de entrevistas",
    "invitaciones de supervisor",
    "autoevaluacion",
    "carta emitida",
    "dirae_status separado",
)

DEMO_USERS = [
    {
        "email": STUDENT_DEMO_EMAIL,
        "rut": "21000001-1",
        "first_name": "Estudiante",
        "last_name": "Demo",
        "role": STUDENT_ROLE,
        "degree": "Ingenieria Civil Informatica",
        "cod_degree": "ICI",
    },
    {
        "email": STUDENT_OTHER_EMAIL,
        "rut": "21000002-1",
        "first_name": "Estudiante",
        "last_name": "Otro",
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
        "email": "superadmin@ufrontera.cl",
        "rut": "21000008-1",
        "first_name": "Superadmin",
        "last_name": "Plataforma",
        "role": SUPERADMIN_ROLE,
    },
]

DEMO_EMAILS = [user["email"] for user in DEMO_USERS] + list(LEGACY_DEMO_EMAILS)
DEMO_ORG_PREFIX = "Demo QA"


@dataclass(frozen=True)
class SeedContext:
    users: dict[str, User]
    roles: dict[str, Role]
    states: dict[str, CurrentState]
    password_hash: str


class DemoSeeder:
    def __init__(self, session: AsyncSession, password: str) -> None:
        self.session = session
        self.password_hash = PasswordService().hash_password(password)
        self.stats: Counter[str] = Counter()

    async def run(self) -> None:
        await self._ensure_role_enum_values()
        roles = await self._ensure_roles()
        users = await self._ensure_users(roles)
        states = await self._get_states()
        context = SeedContext(
            users=users,
            roles=roles,
            states=states,
            password_hash=self.password_hash,
        )
        await self._ensure_induction(context)
        await self._ensure_registration_requirements(context)
        await self._ensure_academic_requirements(context)
        await self._ensure_internships(context)
        await self._ensure_notifications(context)
        await self.session.commit()

    async def clean(self) -> None:
        users = await self._get_demo_users()
        user_ids = [user.id for user in users]

        internship_ids = await self._get_demo_internship_ids(user_ids)
        if internship_ids:
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
            await self.session.execute(
                delete(Notification).where(Notification.recipient_user_id.in_(user_ids))
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
            await self.session.execute(delete(UserRole).where(UserRole.user_id.in_(user_ids)))
            await self.session.execute(delete(User).where(User.id.in_(user_ids)))

        await self.session.commit()
        self.stats["deleted"] += len(user_ids)

    async def _ensure_role_enum_values(self) -> None:
        for role_name in (FICA_ROLE, SUPERADMIN_ROLE):
            await self.session.execute(
                text(f"ALTER TYPE \"enumRole\" ADD VALUE IF NOT EXISTS '{role_name}'")
            )
        await self.session.commit()

    async def _ensure_roles(self) -> dict[str, Role]:
        descriptions = {
            STUDENT_ROLE: "Rol correspondiente a estudiantes en practicas",
            SUPERVISOR_ROLE: "Rol correspondiente al supervisor externo de practicas",
            PRACTICE_MANAGER_ROLE: "Rol correspondiente al encargado de practicas",
            CAREER_DIRECTOR_ROLE: "Rol correspondiente al director de carrera",
            SECRETARY_ROLE: "Rol correspondiente a secretaria de carrera",
            FICA_ROLE: "Rol institucional de consulta agregada transversal",
            SUPERADMIN_ROLE: "Rol tecnico para administracion de usuarios y roles",
        }
        roles: dict[str, Role] = {}
        for role_name in SYSTEM_ROLE_NAMES:
            role = await self._get_role(role_name)
            if role is None:
                role = Role(name=role_name, description=descriptions[role_name])
                self.session.add(role)
                await self.session.flush()
                self.stats["created"] += 1
            elif role.description != descriptions[role_name]:
                role.description = descriptions[role_name]
                self.stats["updated"] += 1
            else:
                self.stats["reused"] += 1
            roles[role_name] = role
        return roles

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
                    degree=data.get("degree"),
                    cod_degree=data.get("cod_degree"),
                    sexo="No definido",
                    is_active=True,
                    is_verified=True,
                )
                self.session.add(user)
                await self.session.flush()
                self.stats["created"] += 1
            else:
                changed = False
                for field_name in ("email", "first_name", "last_name", "rut", "degree", "cod_degree"):
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
        await self._ensure_internship(
            owner=context.users[STUDENT_DEMO_EMAIL],
            status=approved,
            org_name=f"{DEMO_ORG_PREFIX} exportable",
            internship_type=PracticeTypeEnum.practice_1,
            period=PracticePeriodEnum.semester,
            has_school_insurance=True,
            with_documents=True,
        )
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
                start_date=date.today(),
                end_date=date.today() + timedelta(days=60),
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
            )
            self.session.add(internship)
            await self.session.flush()
            self.stats["created"] += 1
        else:
            internship.status_id = status.id
            internship.has_school_insurance = has_school_insurance
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

    async def _ensure_notifications(self, context: SeedContext) -> None:
        recipient = context.users["encargado.practicas@ufrontera.cl"]
        for subject, event_type in (
            ("Demo notificacion no leida", NotificationEventTypeEnum.custom),
            ("Demo documento observado", NotificationEventTypeEnum.requirement_status_changed),
        ):
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
                        content="Notificacion demo generada por seed_demo.py",
                        status=NotificationStatusEnum.simulated,
                        payload={"demo_seed": True},
                    )
                )
                self.stats["created"] += 1
            else:
                self.stats["reused"] += 1

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
        result = await self.session.execute(select(User).where(User.email.in_(DEMO_EMAILS)))
        return list(result.scalars().all())

    async def _get_demo_internship_ids(self, user_ids: list[int]) -> list[int]:
        if not user_ids:
            return []
        result = await self.session.execute(
            select(Internship.id).where(
                Internship.user_id.in_(user_ids),
                Internship.org_name.startswith(DEMO_ORG_PREFIX),
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


def _get_demo_password() -> str:
    password = os.getenv("DEMO_SEED_PASSWORD")
    if not password:
        raise RuntimeError("DEMO_SEED_PASSWORD is required")
    if len(password) < 8:
        raise RuntimeError("DEMO_SEED_PASSWORD must contain at least 8 characters")
    return password


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo QA data")
    parser.add_argument("--clean", action="store_true", help="Remove demo data created by this script")
    args = parser.parse_args()

    _ensure_not_production()
    password = _get_demo_password()

    async with SessionLocal() as session:
        seeder = DemoSeeder(session, password)
        if args.clean:
            await seeder.clean()
        else:
            await seeder.run()
        seeder.print_summary()


if __name__ == "__main__":
    asyncio.run(_main())
