"""Repositorio de acceso a datos para practicas.

Este modulo define `InternshipRepository`, encargado de encapsular consultas y
operaciones de persistencia relacionadas con la entidad `Internship` usando una
sesion asincrona de SQLAlchemy.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi import HTTPException

from app.modules.internships.models.internship_model import Internship
from app.modules.internships.models.current_state_model import CurrentState


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

    async def get_internship_by_id(self, internship_id: int) -> Internship | None:
        """Obtiene una practica por su identificador.

        Args:
            internship_id: Identificador entero de la practica.

        Returns:
            La entidad `Internship` si existe; `None` si no se encuentra.
        """

        query = select(Internship).where(Internship.id == internship_id)
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

    async def get_state_by_title(self, title: str) -> CurrentState:
        result = await self.db.execute(
            select(CurrentState).where(CurrentState.title == title)
        )
        state = result.scalar_one_or_none()
        if state is None:
            raise HTTPException(500, f"Estado '{title}' no encontrado en BD")
        return state

    async def save(self, internship: Internship) -> Internship:
        self.db.add(internship)
        await self.db.commit()
        await self.db.refresh(internship)
        return internship