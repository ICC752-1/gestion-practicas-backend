"""Configuración base de base de datos (SQLAlchemy).

Este módulo centraliza la configuración mínima de SQLAlchemy para la aplicación:

- `Base`: clase base declarativa para modelos ORM.
- `engine`: motor asíncrono creado a partir de `config.DATABASE_URL`.
- `SessionLocal`: factoría de sesiones para crear `AsyncSession` vinculadas al motor.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from collections.abc import AsyncGenerator

from app.core.config import config

class Base(DeclarativeBase):
    """Clase base declarativa para los modelos ORM.

    Las entidades SQLAlchemy del proyecto deberían heredar de esta clase para
    registrarse correctamente en el metadata y habilitar operaciones ORM.
    """

    pass

engine = create_async_engine(config.DATABASE_URL)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Generador de sesiones de base de datos para inyeccion de dependencias.

    Crea una sesion por request y garantiza su cierre al finalizar, 
    incluso si ocurre una excepcion durante el procesamiento 

     Uso en un router:
        @router.get("/ejemplo")
        def mi_endpoint(db: AsyncSession = Depends(get_db)):
            ...

    """
    async with SessionLocal() as session:
        yield session