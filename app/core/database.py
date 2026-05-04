"""Configuracion base de base de datos (SQLAlchemy).

Este modulo centraliza la configuracion minima de SQLAlchemy para la aplicacion:

- `Base`: clase base declarativa para modelos ORM.
- `engine`: motor de conexion creado a partir de `config.DATABASE_URL`.
- `SessionLocal`: factoria de sesiones para crear `Session` vinculadas al motor.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from app.core.config import config

class Base(DeclarativeBase):
    """Clase base declarativa para los modelos ORM.

    Las entidades SQLAlchemy del proyecto deberian heredar de esta clase para
    registrarse correctamente en el metadata y habilitar operaciones ORM.
    """

    pass


# 1. Comenta la línea original (ponle un # al principio)
# SQLALCHEMY_DATABASE_URL = config.DATABASE_URL 

# 2. Escribe esta línea justo debajo con la clave manual
SQLALCHEMY_DATABASE_URL = "postgresql+psycopg://internship_user:your_secure_password@localhost:5432/internship"

# 3. Asegúrate de que el engine use esa variable
engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

def get_db() -> Generator[Session, None, None]:
    """
    Generador de sesiones de base de datos para inyeccion de dependencias.

    Crea una sesion por request y garantiza su cierre al finalizar, 
    incluso si ocurre una excepcion durante el procesamiento 

     Uso en un router:
        @router.get("/ejemplo")
        def mi_endpoint(db: Session = Depends(get_db)):
            ...

    """
    db = SessionLocal()
    try:
        yield db

    finally:
        db.close()