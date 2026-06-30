"""Modelo ORM de usuarios.

Este módulo define la entidad `User` utilizada por el sistema de autenticación y
autorización.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.core.database.database import Base


class User(Base):
    """Representa un usuario del sistema.

    La entidad `User` almacena las credenciales y el estado del usuario, así como
    su relación con roles (normalmente mediante una tabla de asociación como
    `UserRole`).

    Attributes:
        id: Identificador entero del usuario (clave primaria).
        email: Correo electrónico único del usuario.
        password_hash: Hash de la contraseña del usuario.
        first_name: Nombre(s) del usuario.
        last_name: Apellido(s) del usuario.
        rut: Identificador RUT del usuario.
        enrollment: Matrícula institucional del estudiante.
        degree: Carrera o grado academico del usuario.
        cod_degree: Codigo interno de la carrera.
        admission_year: Ano de ingreso del estudiante.
        sexo: Identificador de genero del usuario.
        phone: Telefono de contacto del usuario.
        profession: Profesion del usuario.
        position: Cargo del usuario.
        departament: Departamento del usuario.
        sup_phone: Telefono del supervisor.
        is_active: Indica si la cuenta está activa.
        is_verified: Indica si la cuenta ha sido verificada.
        created_at: Marca temporal (UTC) de creación/última actualización.
        roles: Relación con asignaciones de roles del usuario.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    rut: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    enrollment: Mapped[str | None] = mapped_column(
        String(32),
        unique=True,
        nullable=True,
    )

    degree: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cod_degree: Mapped[str | None] = mapped_column(String(100), nullable=True)
    admission_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sexo: Mapped[str | None] = mapped_column(
        PGEnum(
            "Femenino",
            "Masculino",
            "Otro",
            "No definido",
            name="enumGender",
            create_type=False,
        ),
        nullable=True,
    )
    phone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    profession: Mapped[str | None] = mapped_column(String(100), nullable=True)
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    departament: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sup_phone: Mapped[str | None] = mapped_column(String(100), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    roles = relationship(
        "UserRole", back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    activation_tokens = relationship(
        "AccountActivationToken",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="AccountActivationToken.user_id",
    )
