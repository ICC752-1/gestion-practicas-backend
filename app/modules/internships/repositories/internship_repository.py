"""Repositorio de acceso a datos para practicas.

Este modulo define `InternshipRepository`, encargado de encapsular consultas y
operaciones de persistencia relacionadas con la entidad `Internship` usando una
sesion asincrona de SQLAlchemy.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.internships.models.current_state_model import CurrentState
from app.modules.internships.models.internship_model import Internship
from app.modules.internships.models.internship_status_history_model import (
    InternshipStatusHistory,
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

        return internship

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

        return internship

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
            .options(selectinload(Internship.status))
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

        return internship

    