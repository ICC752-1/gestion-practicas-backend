"""Configuracion base de base de datos (SQLAlchemy).

Este modulo centraliza la configuracion minima de SQLAlchemy para la aplicacion:

- `Base`: clase base declarativa para modelos ORM.
- `engine`: motor asincrono creado a partir de `config.DATABASE_URL`.
- `SessionLocal`: factoria de sesiones para crear `AsyncSession` vinculadas al motor.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import config


class Base(DeclarativeBase):
    """Clase base declarativa para los modelos ORM.

    Las entidades SQLAlchemy del proyecto deberian heredar de esta clase para
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
    """Generador de sesiones de base de datos para inyeccion de dependencias.

    Crea una sesion por request y garantiza su cierre al finalizar,
    incluso si ocurre una excepcion durante el procesamiento.

    Uso en un router:
        @router.get("/ejemplo")
        def mi_endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """

    async with SessionLocal() as session:
        yield session
