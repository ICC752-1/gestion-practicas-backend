"""Modelo ORM de practicas.

Este modulo define la entidad `Internship`, utilizada para representar la
informacion base de una practica profesional asociada a un estudiante.
"""

from datetime import date, datetime, timezone
import enum
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base

class PracticePeriodEnum(str, enum.Enum):
    """Enumeración de periodos académicos para las prácticas"""
    semester = "Semestre"
    summer = "Verano"
    winter = "Invierno"

class PracticeTypeEnum(str, enum.Enum):
    """Enumeración de tipos de práctica según el plan de estudios"""
    practice_1 = "Práctica de Estudio I"
    practice_2 = "Práctica de Estudio II"
    controlled_practice = "Práctica Controlada"
    thesis = "Tesis"

class Internship(Base):
    """Representa una practica profesional registrada en el sistema.

    Attributes:
        id: Identificador entero de la practica.
        org_name: Nombre de la organizacion donde se realiza la practica.
        sector: Sector o rubro de la organizacion.
        address: Direccion principal de la organizacion.
        city: Ciudad donde se ubica la organizacion.
        org_phone: Telefono de contacto de la organizacion, si existe.
        web: Sitio web de la organizacion, si existe.
        start_date: Fecha de inicio de la practica.
        end_date: Fecha de termino de la practica.
        schedule: Horario definido para la practica.
        days: Dias en que se realizara la practica.
        modality: Modalidad de la practica segun `enumModality`.
        internship_address: Direccion especifica donde se ejecutara la practica.
        act_description: Descripcion de actividades a realizar.
        ben_description: Descripcion del beneficio o aporte esperado.
        amount: Monto asociado a la practica, si corresponde.
        upload_date: Fecha y hora de registro.
        status_id: Identificador del estado actual, si existe.
        user_id: Identificador del estudiante propietario.
        internship_period: Periodo de la practic según `enumPeriod`.
        internship_type: Tipo de la practica según `enumInternshipType`.
        has_school_insure: Booleanno que indica si posee seguro escolar.
        status: Relacion ORM hacia `CurrentState`.
        student: Relacion ORM hacia `User`.
    """

    __tablename__ = "internship"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(255), nullable=False)
    org_phone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    web: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    schedule: Mapped[str] = mapped_column(String(255), nullable=False)
    days: Mapped[str] = mapped_column(String(255), nullable=False)
    modality: Mapped[str] = mapped_column(
        PGEnum(
            "Presencial",
            "Remoto",
            "Hibrido",
            name="enumModality",
            create_type=False,
        ),
        nullable=False,
    )
    internship_address: Mapped[str] = mapped_column(String(255), nullable=False)
    act_description: Mapped[str] = mapped_column(String(255), nullable=False)
    ben_description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upload_date: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.utcnow(),
        nullable=False,
    )
    status_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("currentstate.id"),
        nullable=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    internship_period: Mapped[PracticePeriodEnum] = mapped_column(
        PGEnum(
            "Semestre",
            "Verano",
            "Invierno",
            name="enumInternshipPeriod",
            create_type=False,
        ),
    nullable=False,
    )
    
    internship_type: Mapped[PracticeTypeEnum] = mapped_column(
        PGEnum(
            "Práctica de Estudio I",
            "Práctica de Estudio II",
            "Práctica Controlada",
            "Tesis",
            name="enumStudentInternshipType",
            create_type=False,
        ),
        nullable=False,
    )
    
    has_school_insurance: Mapped[bool] = mapped_column(
        Boolean, 
        default=False,
        nullable=False,
    )

    status = relationship("CurrentState", back_populates="internships")
    student = relationship("User")
