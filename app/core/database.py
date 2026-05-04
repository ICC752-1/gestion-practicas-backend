"""Configuración base de base de datos (SQLAlchemy).

Este módulo centraliza la configuración mínima de SQLAlchemy para la aplicación:

- `Base`: clase base declarativa para modelos ORM.
- `engine`: motor asíncrono creado a partir de `config.DATABASE_URL`.
- `SessionLocal`: factoría de sesiones para crear `AsyncSession` vinculadas al motor.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from typing import Generator

from app.core.config import config

class Base(DeclarativeBase):
    """Clase base declarativa para los modelos ORM.

    Las entidades SQLAlchemy del proyecto deberían heredar de esta clase para
    registrarse correctamente en el metadata y habilitar operaciones ORM.
    """

    pass

# 1. Comenta la línea original (ponle un # al principio)
# SQLALCHEMY_DATABASE_URL = config.DATABASE_URL 

# 2. Escribe esta línea justo debajo con la clave manual
SQLALCHEMY_DATABASE_URL = "postgresql+psycopg://internship_user:your_secure_password@localhost:5432/internship"

engine = create_async_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

def get_db() -> Generator[AsyncSession, None, None]:
    """
    Generador de sesiones de base de datos para inyeccion de dependencias.

    Crea una sesion por request y garantiza su cierre al finalizar, 
    incluso si ocurre una excepcion durante el procesamiento 

     Uso en un router:
        @router.get("/ejemplo")
        def mi_endpoint(db: AsyncSession = Depends(get_db)):
            ...

    """
    db = SessionLocal()
    try:
        yield db

    finally:
        db.close()