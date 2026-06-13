"""Repositorio de acceso a datos para practicas.

Este modulo define `InternshipRepository`, encargado de encapsular consultas y
operaciones de persistencia relacionadas con la entidad `Internship` usando una
sesion asincrona de SQLAlchemy.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models.role_model import Role
from app.modules.auth.models.user_model import User
from app.modules.auth.models.user_role_model import UserRole
from app.modules.internships.models.current_state_model import CurrentState
from app.modules.internships.models.induction_model import (
    InductionAttempt,
    InductionContentVersion,
)
from app.modules.internships.models.internship_exception_model import InternshipException
from app.modules.internships.models.internship_model import Internship
from app.modules.internships.models.internship_status_history_model import (
    InternshipStatusHistory,
)
from app.modules.internships.models.student_internship_requirement_model import (
    StudentInternshipRequirement,
    StudentRegistrationRequirement,
)


class InternshipRepository:
    """Implementa operaciones de lectura y escritura sobre practicas.

    Attributes:
        db: Sesion asincrona (`AsyncSession`) utilizada para ejecutar consultas
            y confirmar transacciones.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el repositorio con una sesion de base de datos.

        Args:
            db: Sesion asincrona de SQLAlchemy.
        """

        self.db = db

    async def create_internship(self, internship: Internship) -> Internship:
        """Persiste una practica en la base de datos.

        Agrega la entidad a la sesion, confirma la transaccion y refresca la
        instancia para asegurar que campos generados por la base de datos queden
        disponibles en el objeto.

        Args:
            internship: Entidad `Internship` a crear.

        Returns:
            La misma entidad `Internship` persistida y refrescada.
        """

        self.db.add(internship)
        await self.db.commit()
        await self.db.refresh(internship)

        loaded_internship = await self.get_internship_by_id(internship.id)
        if loaded_internship is None:
            return internship

        return loaded_internship

    async def create_internship_with_history(
        self,
        internship: Internship,
        initial_status: CurrentState,
        actor_id: int,
        reason: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> Internship:
        """Persiste una practica y registra su estado inicial.

        Args:
            internship: Entidad `Internship` a crear.
            initial_status: Estado inicial que se asignara a la practica.
            actor_id: Identificador del usuario que crea la practica.
            reason: Motivo funcional registrado en el historial.
            metadata: Datos auxiliares de contexto, si existen.

        Returns:
            La practica persistida con su estado actual asignado.
        """

        internship.status_id = initial_status.id
        self.db.add(internship)
        await self.db.flush()

        status_history = InternshipStatusHistory(
            internship_id=internship.id,
            previous_status_id=None,
            new_status_id=initial_status.id,
            actor_id=actor_id,
            reason=reason,
            metadata_json=metadata,
        )
        self.db.add(status_history)
        await self.db.commit()
        await self.db.refresh(internship)

        loaded_internship = await self.get_internship_by_id(internship.id)
        if loaded_internship is None:
            return internship

        return loaded_internship

    async def get_internship_by_id(self, internship_id: int) -> Internship | None:
        """Obtiene una practica por su identificador.

        Args:
            internship_id: Identificador entero de la practica.

        Returns:
            La entidad `Internship` si existe; `None` si no se encuentra.
        """

        query = (
            select(Internship)
            .where(Internship.id == internship_id)
            .options(
                selectinload(Internship.status),
                selectinload(Internship.student),
                selectinload(Internship.exceptions),
            )
        )
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def get_state_by_title(self, title: str) -> CurrentState | None:
        """Obtiene un estado de practica por su titulo exacto.

        Args:
            title: Nombre funcional del estado.

        Returns:
            `CurrentState` si existe; `None` si no se encuentra.
        """

        query = select(CurrentState).where(CurrentState.title == title)
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def list_internships_by_user(self, user_id: int) -> list[Internship]:
        """Lista practicas asociadas a un usuario.

        La consulta retorna las practicas ordenadas desde la mas reciente segun
        `upload_date`.

        Args:
            user_id: Identificador entero del usuario propietario.

        Returns:
            Lista de entidades `Internship` asociadas al usuario.
        """

        query = (
            select(Internship)
            .where(Internship.user_id == user_id)
            .options(
                selectinload(Internship.status),
                selectinload(Internship.exceptions),
            )
            .order_by(Internship.upload_date.desc())
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def list_dashboard_internships(self) -> list[Internship]:
        """Lista practicas con relaciones necesarias para dashboard coordinador.

        Returns:
            Lista de practicas con estudiante y estado actual precargados.
        """

        query = (
            select(Internship)
            .options(
                selectinload(Internship.student),
                selectinload(Internship.status),
            )
            .order_by(Internship.upload_date.desc(), Internship.id.desc())
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def list_users_by_roles(self, role_names: set[str]) -> list[User]:
        """Lista usuarios activos que poseen alguno de los roles indicados."""

        query = (
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.name.in_(role_names), User.is_active.is_(True))
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .order_by(User.id.asc())
        )
        result = await self.db.execute(query)

        return list(result.scalars().unique().all())

    async def list_internship_status_history(
        self,
        internship_id: int,
    ) -> list[InternshipStatusHistory]:
        """Lista el historial de estados de una practica.

        Args:
            internship_id: Identificador entero de la practica.

        Returns:
            Entradas de historial ordenadas cronologicamente.
        """

        query = (
            select(InternshipStatusHistory)
            .where(InternshipStatusHistory.internship_id == internship_id)
            .options(
                selectinload(InternshipStatusHistory.previous_status),
                selectinload(InternshipStatusHistory.new_status),
                selectinload(InternshipStatusHistory.actor),
            )
            .order_by(
                InternshipStatusHistory.changed_at.asc(),
                InternshipStatusHistory.id.asc(),
            )
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def update_internship_status_with_history(
        self,
        internship: Internship,
        previous_status: CurrentState | None,
        new_status: CurrentState,
        actor_id: int,
        reason: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> Internship:
        """Actualiza el estado actual y registra una entrada de historial.

        Args:
            internship: Practica que sera actualizada.
            previous_status: Estado anterior de la practica, si existia.
            new_status: Estado nuevo de la practica.
            actor_id: Usuario que ejecuta la transicion.
            reason: Motivo funcional de la transicion.
            metadata: Datos auxiliares de contexto, si existen.

        Returns:
            Practica actualizada.
        """

        internship.status_id = new_status.id
        status_history = InternshipStatusHistory(
            internship_id=internship.id,
            previous_status_id=None if previous_status is None else previous_status.id,
            new_status_id=new_status.id,
            actor_id=actor_id,
            reason=reason,
            metadata_json=metadata,
        )
        self.db.add(status_history)
        await self.db.commit()
        await self.db.refresh(internship)

        loaded_internship = await self.get_internship_by_id(internship.id)
        if loaded_internship is None:
            return internship

        return loaded_internship

    async def update_internship_admin_fields_with_history(
        self,
        internship: Internship,
        updates: dict[str, Any],
        actor_id: int,
        reason: str,
        changed_fields: list[str],
    ) -> Internship:
        """Actualiza campos administrativos y registra trazabilidad."""

        for field_name, value in updates.items():
            setattr(internship, field_name, value)

        status_history = InternshipStatusHistory(
            internship_id=internship.id,
            previous_status_id=internship.status_id,
            new_status_id=internship.status_id,
            actor_id=actor_id,
            reason=reason,
            metadata_json={
                "action": "admin_update",
                "changed_fields": changed_fields,
            },
        )
        self.db.add(status_history)
        await self.db.commit()
        await self.db.refresh(internship)

        return internship

    async def cancel_internship_with_history(
        self,
        internship: Internship,
        actor_id: int,
        reason: str,
    ) -> Internship:
        """Marca una practica como anulada y registra trazabilidad."""

        internship.is_cancelled = True
        internship.cancelled_at = datetime.now(UTC).replace(tzinfo=None)
        internship.cancelled_by = actor_id
        internship.cancellation_reason = reason

        status_history = InternshipStatusHistory(
            internship_id=internship.id,
            previous_status_id=internship.status_id,
            new_status_id=internship.status_id,
            actor_id=actor_id,
            reason=reason,
            metadata_json={"action": "cancel"},
        )
        self.db.add(status_history)
        await self.db.commit()
        await self.db.refresh(internship)

        return internship

    async def get_exception_by_rule(
        self,
        internship_id: int,
        rule: str,
    ) -> InternshipException | None:
        """Obtiene una excepcion existente para una practica y regla dados.

        Se utiliza para evitar registrar excepciones duplicadas sobre la
        misma regla en la misma practica.

        Args:
            internship_id: Identificador de la practica.
            rule: Nombre canonico de la regla exceptuada.

        Returns:
            La excepcion existente o ``None`` si no existe.
        """
        result = await self.db.execute(
            select(InternshipException)
            .where(
                InternshipException.internship_id == internship_id,
                InternshipException.rule == rule,
            )
            .options(selectinload(InternshipException.actor))
        )
        return result.scalar_one_or_none()

    async def create_exception(
        self,
        internship_id: int,
        rule: str,
        reason: str,
        authorized_by: int,
    ) -> InternshipException:
        """Persiste una excepcion administrativa para una practica.

        Args:
            internship_id: Identificador de la practica.
            rule: Regla de negocio exceptuada.
            reason: Justificacion del actor.
            authorized_by: Identificador del usuario autorizador.

        Returns:
            La excepcion persistida y refrescada.
        """
        exception = InternshipException(
            internship_id=internship_id,
            rule=rule,
            reason=reason,
            authorized_by=authorized_by,
        )
        self.db.add(exception)
        await self.db.commit()
        await self.db.refresh(exception, ["actor"])
        return exception

    async def list_exceptions(
        self,
        internship_id: int,
    ) -> list[InternshipException]:
        """Lista todas las excepciones registradas para una practica.

        Args:
            internship_id: Identificador de la practica.

        Returns:
            Lista de excepciones ordenadas por fecha de autorizacion.
        """
        result = await self.db.execute(
            select(InternshipException)
            .where(InternshipException.internship_id == internship_id)
            .options(selectinload(InternshipException.actor))
            .order_by(InternshipException.authorized_at.asc())
        )
        return list(result.scalars().all())

    # ── Inducción ──────────────────────────────────────────────────────────

    async def get_active_induction_content(
        self,
    ) -> InductionContentVersion | None:
        """Obtiene la versión de contenido de inducción activa y publicada.

        Returns:
            ``InductionContentVersion`` con videos y preguntas, o ``None``
            si no existe una versión activa publicada.
        """
        query = (
            select(InductionContentVersion)
            .where(
                InductionContentVersion.is_active.is_(True),
                InductionContentVersion.status == "published",
            )
            .options(
                selectinload(InductionContentVersion.videos),
                selectinload(InductionContentVersion.questions),
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_induction_content_version_by_id(
        self,
        version_id: int,
    ) -> InductionContentVersion | None:
        """Obtiene una versión de contenido por su identificador.

        Args:
            version_id: Identificador de la versión.

        Returns:
            ``InductionContentVersion`` o ``None``.
        """
        query = (
            select(InductionContentVersion)
            .where(InductionContentVersion.id == version_id)
            .options(
                selectinload(InductionContentVersion.questions),
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_induction_attempt(
        self,
        attempt: InductionAttempt,
    ) -> InductionAttempt:
        """Persiste un intento de cuestionario de inducción.

        Args:
            attempt: Entidad ``InductionAttempt`` a persistir.

        Returns:
            El intento persistido y refrescado.
        """
        self.db.add(attempt)
        await self.db.commit()
        await self.db.refresh(attempt)
        return attempt

    async def get_passed_induction_attempt(
        self,
        user_id: int,
    ) -> InductionAttempt | None:
        """Obtiene el último intento aprobado de inducción de un estudiante.

        Args:
            user_id: Identificador del estudiante.

        Returns:
            El intento aprobado más reciente, o ``None``.
        """
        result = await self.db.execute(
            select(InductionAttempt)
            .where(
                InductionAttempt.user_id == user_id,
                InductionAttempt.passed.is_(True),
            )
            .order_by(InductionAttempt.attempted_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    # ── Prerrequisitos del estudiante ──────────────────────────────────────

    async def get_student_requirement(
        self,
        user_id: int,
        requirement: str,
    ) -> StudentRegistrationRequirement | None:
        """Obtiene el registro de un prerrequisito para un estudiante.

        Args:
            user_id: Identificador del estudiante.
            requirement: Nombre del requisito (``"school_insurance"`` o
                ``"induction"``).

        Returns:
            ``StudentRegistrationRequirement`` si existe, o ``None``.
        """
        result = await self.db.execute(
            select(StudentRegistrationRequirement)
            .where(
                StudentRegistrationRequirement.user_id == user_id,
                StudentRegistrationRequirement.requirement == requirement,
            )
        )
        return result.scalar_one_or_none()

    async def get_academic_requirement(
        self,
        user_id: int,
        practice_type: str,
    ) -> StudentInternshipRequirement | None:
        result = await self.db.execute(
            select(StudentInternshipRequirement)
            .where(
                StudentInternshipRequirement.user_id == user_id,
                StudentInternshipRequirement.type == practice_type,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_academic_requirement_status(
        self,
        user_id: int,
        practice_type: str,
        new_status: str,
        updated_by: int,
    ) -> StudentInternshipRequirement:
        existing = await self.get_academic_requirement(user_id, practice_type)

        if existing is None:
            req = StudentInternshipRequirement(
                user_id=user_id,
                type=practice_type,
                status=new_status,
                status_updated_at=datetime.now(UTC),
                status_updated_by=updated_by,
            )
            self.db.add(req)
            await self.db.commit()
            await self.db.refresh(req)
            return req

        existing.status = new_status
        existing.status_updated_at = datetime.now(UTC)
        existing.status_updated_by = updated_by
        await self.db.commit()
        await self.db.refresh(existing)
        return existing
