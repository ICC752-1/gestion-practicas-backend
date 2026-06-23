"""Repositorio de agenda para bloques de entrevistas y presentaciones."""

from datetime import date, time

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models.role_model import Role
from app.modules.auth.models.user_model import User
from app.modules.auth.models.user_role_model import UserRole
from app.modules.documents.models.document_model import Document
from app.modules.internships.models.internship_model import Internship
from app.modules.scheduling.models.presentation_model import (
    Presentation,
    PresentationPurposeEnum,
    PresentationStatusEnum,
)
from app.modules.scheduling.models.scheduling_config_model import SchedulingConfig
from app.modules.scheduling.models.scheduling_request_model import SchedulingRequest
from app.modules.supervisor_evaluations.models.supervisor_evaluation_model import (
    SupervisorEvaluation,
)


ADMIN_ROLE_NAMES = {"Encargado de practica", "Director de carrera"}


ACTIVE_BLOCK_STATUSES = (
    PresentationStatusEnum.available,
    PresentationStatusEnum.scheduled,
    PresentationStatusEnum.completed,
    PresentationStatusEnum.no_show,
)

VISIBLE_APPOINTMENT_STATUSES = (
    PresentationStatusEnum.scheduled,
    PresentationStatusEnum.completed,
    PresentationStatusEnum.no_show,
)


class SchedulingRepository:
    """Encapsula lecturas y escrituras de agenda."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_slots(self, slots: list[Presentation]) -> list[Presentation]:
        """Persiste una lista de bloques de disponibilidad."""

        self.db.add_all(slots)
        await self.db.commit()

        for slot in slots:
            await self.db.refresh(slot)

        return slots

    async def save_slot(self, slot: Presentation) -> Presentation:
        """Confirma los cambios de un bloque existente."""

        await self.db.commit()
        await self.db.refresh(slot)
        refetched = await self.get_slot_by_id(slot.id)
        return refetched or slot

    async def save_slots(self, slots: list[Presentation]) -> list[Presentation]:
        """Confirma cambios de varios bloques en una misma transaccion."""

        await self.db.commit()

        for slot in slots:
            await self.db.refresh(slot)

        return slots

    async def delete_slot(self, slot: Presentation) -> None:
        """Elimina un bloque de disponibilidad."""

        await self.db.delete(slot)
        await self.db.commit()

    async def get_slot_by_id(self, slot_id: int) -> Presentation | None:
        """Obtiene un bloque por identificador."""

        query = (
            select(Presentation)
            .where(Presentation.id == slot_id)
            .options(
                selectinload(Presentation.internship),
                selectinload(Presentation.student),
                selectinload(Presentation.owner).selectinload(User.roles).selectinload(UserRole.role),
                selectinload(Presentation.document).selectinload(Document.document_type),
            )
        )
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def get_slot_by_id_for_update(self, slot_id: int) -> Presentation | None:
        """Obtiene un bloque con bloqueo de fila para evitar dobles reservas."""

        query = (
            select(Presentation)
            .where(Presentation.id == slot_id)
            .with_for_update()
            .options(
                selectinload(Presentation.internship),
                selectinload(Presentation.student),
                selectinload(Presentation.owner).selectinload(User.roles).selectinload(UserRole.role),
                selectinload(Presentation.document).selectinload(Document.document_type),
            )
        )
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def get_internship_by_id(self, internship_id: int) -> Internship | None:
        """Obtiene una practica por identificador."""

        query = select(Internship).where(Internship.id == internship_id)
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def list_available_slots(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        purpose: PresentationPurposeEnum | None = None,
    ) -> list[Presentation]:
        """Lista bloques publicados disponibles."""

        query = (
            select(Presentation)
            .where(Presentation.status == PresentationStatusEnum.available)
            .options(
                selectinload(Presentation.owner).selectinload(User.roles).selectinload(UserRole.role),
            )
        )

        if date_from is not None:
            query = query.where(Presentation.date >= date_from)

        if date_to is not None:
            query = query.where(Presentation.date <= date_to)

        if purpose is not None:
            query = query.where(Presentation.purpose == purpose)

        query = query.order_by(Presentation.date.asc(), Presentation.start_time.asc())
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def list_appointments_for_owner(self, owner_id: int) -> list[Presentation]:
        """Lista citas agendadas con un administrativo especifico."""

        query = (
            select(Presentation)
            .where(
                Presentation.owner_id == owner_id,
                Presentation.status.in_(VISIBLE_APPOINTMENT_STATUSES),
            )
            .options(
                selectinload(Presentation.internship),
                selectinload(Presentation.student),
                selectinload(Presentation.owner).selectinload(User.roles).selectinload(UserRole.role),
                selectinload(Presentation.document).selectinload(Document.document_type),
            )
            .order_by(Presentation.date.asc(), Presentation.start_time.asc())
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def list_appointments_for_student(self, user_id: int) -> list[Presentation]:
        """Lista citas agendadas por un estudiante."""

        query = (
            select(Presentation)
            .where(
                Presentation.user_id == user_id,
                Presentation.status.in_(VISIBLE_APPOINTMENT_STATUSES),
            )
            .options(
                selectinload(Presentation.internship),
                selectinload(Presentation.owner).selectinload(User.roles).selectinload(UserRole.role),
                selectinload(Presentation.document).selectinload(Document.document_type),
            )
            .order_by(Presentation.date.asc(), Presentation.start_time.asc())
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def has_owner_overlap(
        self,
        owner_id: int,
        slot_date: date,
        start_time: time,
        end_time: time,
        exclude_slot_id: int | None = None,
    ) -> bool:
        """Indica si el administrativo ya tiene un bloque solapado."""

        query = select(Presentation.id).where(
            Presentation.owner_id == owner_id,
            Presentation.date == slot_date,
            Presentation.status.in_(ACTIVE_BLOCK_STATUSES),
            Presentation.start_time < end_time,
            Presentation.end_time > start_time,
        )

        if exclude_slot_id is not None:
            query = query.where(Presentation.id != exclude_slot_id)

        result = await self.db.execute(query.limit(1))

        return result.scalar_one_or_none() is not None

    async def has_supervisor_evaluation(self, internship_id: int) -> bool:
        """Indica si la practica ya cuenta con evaluacion de supervisor."""

        query = select(SupervisorEvaluation.id).where(
            SupervisorEvaluation.internship_id == internship_id
        )
        result = await self.db.execute(query.limit(1))

        return result.scalar_one_or_none() is not None

    async def has_student_overlap(
        self,
        user_id: int,
        slot_date: date,
        start_time: time,
        end_time: time,
        exclude_slot_id: int | None = None,
    ) -> bool:
        """Indica si el estudiante ya tiene una cita solapada."""

        query = select(Presentation.id).where(
            Presentation.user_id == user_id,
            Presentation.date == slot_date,
            Presentation.status == PresentationStatusEnum.scheduled,
            Presentation.start_time < end_time,
            Presentation.end_time > start_time,
        )

        if exclude_slot_id is not None:
            query = query.where(Presentation.id != exclude_slot_id)

        result = await self.db.execute(query.limit(1))

        return result.scalar_one_or_none() is not None

    async def has_active_appointment_for_internship(
        self,
        internship_id: int,
        purpose: PresentationPurposeEnum,
    ) -> bool:
        """Indica si la practica ya tiene una cita vigente para ese proposito."""

        query = select(Presentation.id).where(
            Presentation.internship_id == internship_id,
            Presentation.purpose == purpose,
            Presentation.status == PresentationStatusEnum.scheduled,
        )
        result = await self.db.execute(query.limit(1))

        return result.scalar_one_or_none() is not None

    async def create_scheduling_request(self, request: SchedulingRequest) -> SchedulingRequest:
        """Crea y persiste una nueva solicitud de agendamiento."""
        self.db.add(request)
        await self.db.commit()
        await self.db.refresh(request)
        refetched = await self.get_scheduling_request_by_id(request.id)
        return refetched or request

    async def get_scheduling_request_by_id(self, request_id: int) -> SchedulingRequest | None:
        """Obtiene una solicitud de agendamiento por ID con relaciones cargadas."""
        query = (
            select(SchedulingRequest)
            .where(SchedulingRequest.id == request_id)
            .options(
                selectinload(SchedulingRequest.student).selectinload(User.roles).selectinload(UserRole.role),
                selectinload(SchedulingRequest.coordinator).selectinload(User.roles).selectinload(UserRole.role),
                selectinload(SchedulingRequest.target_coordinator).selectinload(User.roles).selectinload(UserRole.role),
                selectinload(SchedulingRequest.internship),
                selectinload(SchedulingRequest.presentation),
                selectinload(SchedulingRequest.document).selectinload(Document.document_type),
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_requests_for_student(self, student_id: int) -> list[SchedulingRequest]:
        """Obtiene todas las solicitudes de agendamiento de un estudiante."""
        query = (
            select(SchedulingRequest)
            .where(SchedulingRequest.student_id == student_id)
            .options(
                selectinload(SchedulingRequest.student).selectinload(User.roles).selectinload(UserRole.role),
                selectinload(SchedulingRequest.coordinator).selectinload(User.roles).selectinload(UserRole.role),
                selectinload(SchedulingRequest.target_coordinator).selectinload(User.roles).selectinload(UserRole.role),
                selectinload(SchedulingRequest.internship),
                selectinload(SchedulingRequest.presentation),
                selectinload(SchedulingRequest.document).selectinload(Document.document_type),
            )
            .order_by(SchedulingRequest.created_at.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_pending_requests(
        self, actor_id: int | None = None
    ) -> list[SchedulingRequest]:
        """Obtiene las solicitudes pendientes de agendamiento.

        Cuando ``actor_id`` se proporciona, filtra las solicitudes dirigidas al
        coordinador autenticado (``target_coordinator_id == actor_id``) o a
        solicitudes legacy sin destinatario explícito
        (``target_coordinator_id IS NULL``).
        """

        query = select(SchedulingRequest).where(SchedulingRequest.status == "pending")

        if actor_id is not None:
            query = query.where(
                or_(
                    SchedulingRequest.target_coordinator_id == actor_id,
                    SchedulingRequest.target_coordinator_id.is_(None),
                )
            )

        query = query.options(
            selectinload(SchedulingRequest.student).selectinload(User.roles).selectinload(UserRole.role),
            selectinload(SchedulingRequest.coordinator).selectinload(User.roles).selectinload(UserRole.role),
            selectinload(SchedulingRequest.target_coordinator).selectinload(User.roles).selectinload(UserRole.role),
            selectinload(SchedulingRequest.internship),
            selectinload(SchedulingRequest.presentation),
            selectinload(SchedulingRequest.document).selectinload(Document.document_type),
        ).order_by(SchedulingRequest.created_at.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())


    async def save_scheduling_request(self, request: SchedulingRequest) -> SchedulingRequest:
        """Guarda cambios en una solicitud de agendamiento."""
        await self.db.commit()
        await self.db.refresh(request)
        refetched = await self.get_scheduling_request_by_id(request.id)
        return refetched or request

    async def get_scheduling_config(self, coordinator_id: int) -> SchedulingConfig | None:
        """Obtiene la configuración de agendamiento de un coordinador."""
        query = select(SchedulingConfig).where(SchedulingConfig.coordinator_id == coordinator_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def has_any_general_consultation_enabled(self) -> bool:
        """Indica si al menos un coordinador tiene habilitadas las consultas generales."""
        query = select(SchedulingConfig.id).where(SchedulingConfig.general_consultations_enabled.is_(True)).limit(1)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def is_internship_applications_disabled(self) -> bool:
        """Indica si la inscripción de prácticas está globalmente desactivada.

        El flag ``internship_applications_disabled`` se almacena por-coordinador,
        pero semánticamente es global: sólo el ``Director de carrera`` puede
        modificarlo. Se consulta si existe algún registro con el flag en ``True``.
        """
        query = (
            select(SchedulingConfig.id)
            .where(SchedulingConfig.internship_applications_disabled.is_(True))
            .limit(1)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def list_active_coordinators_for_consultations(self) -> list[User]:
        """Lista coordinadores con consultas generales habilitadas.

        Retorna usuarios activos con rol administrativo que tienen
        ``general_consultations_enabled == True`` en su configuración, con sus
        roles cargados para que el esquema pueda serializar ``role_name``.
        """
        query = (
            select(User)
            .join(SchedulingConfig, SchedulingConfig.coordinator_id == User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                SchedulingConfig.general_consultations_enabled.is_(True),
                User.is_active.is_(True),
                Role.name.in_(ADMIN_ROLE_NAMES),
            )
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .order_by(User.id.asc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().unique().all())

    async def upsert_scheduling_config(
        self,
        coordinator_id: int,
        general_consultations_enabled: bool | None = None,
        internship_applications_disabled: bool | None = None,
    ) -> SchedulingConfig:
        """Crea o actualiza selectivamente la configuración de un coordinador.

        Solo actualiza los campos que reciban un valor distinto de ``None``,
        preservando los demás. Al menos uno de los dos campos debe estar
        definido.
        """
        config = await self.get_scheduling_config(coordinator_id)
        if config is None:
            config = SchedulingConfig(
                coordinator_id=coordinator_id,
                general_consultations_enabled=(
                    general_consultations_enabled
                    if general_consultations_enabled is not None
                    else False
                ),
                internship_applications_disabled=(
                    internship_applications_disabled
                    if internship_applications_disabled is not None
                    else False
                ),
            )
            self.db.add(config)
        else:
            if general_consultations_enabled is not None:
                config.general_consultations_enabled = general_consultations_enabled
            if internship_applications_disabled is not None:
                config.internship_applications_disabled = (
                    internship_applications_disabled
                )
        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def get_supervisor_evaluation_recommendation(self, internship_id: int) -> str | None:
        """Obtiene la recomendación de la evaluación del supervisor para una práctica."""
        query = select(SupervisorEvaluation.recommendation).where(
            SupervisorEvaluation.internship_id == internship_id
        )
        result = await self.db.execute(query)
        return result.scalar()

    async def has_self_evaluation(self, internship_id: int) -> bool:
        """Indica si el estudiante ya completó y envió su autoevaluación."""
        from app.modules.self_evaluations.models.self_evaluation_model import (
            SelfEvaluation,
            SelfEvaluationStatusEnum,
        )
        query = select(SelfEvaluation.id).where(
            SelfEvaluation.internship_id == internship_id,
            SelfEvaluation.status == SelfEvaluationStatusEnum.submitted,
        )
        result = await self.db.execute(query.limit(1))
        return result.scalar_one_or_none() is not None

    async def get_scheduling_request_by_presentation_id(
        self,
        presentation_id: int,
    ) -> SchedulingRequest | None:
        """Obtiene la solicitud de agendamiento asociada a una presentación."""
        query = (
            select(SchedulingRequest)
            .where(SchedulingRequest.presentation_id == presentation_id)
            .options(
                selectinload(SchedulingRequest.student).selectinload(User.roles).selectinload(UserRole.role),
                selectinload(SchedulingRequest.coordinator).selectinload(User.roles).selectinload(UserRole.role),
                selectinload(SchedulingRequest.target_coordinator).selectinload(User.roles).selectinload(UserRole.role),
                selectinload(SchedulingRequest.internship),
                selectinload(SchedulingRequest.presentation),
                selectinload(SchedulingRequest.document).selectinload(Document.document_type),
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()


