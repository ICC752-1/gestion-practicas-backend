"""Configuración base de base de datos (SQLAlchemy).

Este módulo centraliza la configuración mínima de SQLAlchemy para la aplicación:

- `Base`: clase base declarativa para modelos ORM.
- `engine`: motor de conexión creado a partir de `config.DATABASE_URL`.
- `SessionLocal`: factoría de sesiones para crear `Session` vinculadas al motor.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import config


class Base(DeclarativeBase):
    """Clase base declarativa para los modelos ORM.

    Las entidades SQLAlchemy del proyecto deberían heredar de esta clase para
    registrarse correctamente en el metadata y habilitar operaciones ORM.
    """

    pass

engine = create_engine(config.DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)