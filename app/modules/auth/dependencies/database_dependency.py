"""Dependencia de base de datos para inyección (FastAPI).

Este módulo expone `get_db`, un generador asíncrono que entrega una sesión de
SQLAlchemy por request y garantiza su correcto cierre.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Entrega una sesión de base de datos usando un contexto asíncrono.

    Yields:
        Instancia de `AsyncSession` lista para ejecutar consultas.
    """

    async with SessionLocal() as session:
        yield session
        