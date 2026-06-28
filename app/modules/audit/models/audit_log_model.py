"""Modelo ORM para eventos persistidos en LogAction."""

from datetime import datetime
import enum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base


class AuditActionEnum(str, enum.Enum):
    """Acciones auditadas por los triggers de base de datos."""

    insert = "INSERT"
    update = "UPDATE"
    delete = "DELETE"


class AuditEntityEnum(str, enum.Enum):
    """Entidades auditables declaradas en init.sql."""

    user = "Usuario"
    internship = "Práctica"
    document = "Documento"
    presentation = "Presentación"
    state = "Estado"
    role = "Rol"
    config = "Configuración"
    self_evaluation = "Autoevaluación"
    portability = "Portabilidad"


class AuditLog(Base):
    """Fila de auditoria transversal generada por triggers o eventos de negocio."""

    __tablename__ = "logaction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[AuditActionEnum] = mapped_column(
        PGEnum(
            AuditActionEnum,
            name="enumAction",
            values_callable=lambda enum_class: [item.value for item in enum_class],
            create_type=False,
        ),
        nullable=False,
    )
    entity: Mapped[AuditEntityEnum] = mapped_column(
        PGEnum(
            AuditEntityEnum,
            name="enumEntity",
            values_callable=lambda enum_class: [item.value for item in enum_class],
            create_type=False,
        ),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    actor = relationship("User")
