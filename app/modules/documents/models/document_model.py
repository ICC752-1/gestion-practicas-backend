"""Modelos ORM para documentos de practica.

Este modulo define las entidades `DocumentType` y `Document`, usadas para
persistir metadatos documentales asociados a una practica. Los archivos fisicos
se almacenan fuera de la base de datos y `file_path` se trata como una clave
interna de storage, no como URL publica.
"""

from datetime import UTC, datetime
import enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.database import Base


class DocumentCategoryEnum(str, enum.Enum):
    """Categorias funcionales de tipos documentales."""

    academic = "Académico"
    administrative = "Administrativo"


class DocumentExtensionEnum(str, enum.Enum):
    """Extensiones de archivo permitidas para documentos."""

    pdf = "pdf"
    docx = "docx"
    jpg = "jpg"
    png = "png"
    zip = "zip"


class DocumentStatusEnum(str, enum.Enum):
    """Estados internos de un documento."""

    uploaded = "uploaded"
    observed = "observed"
    approved = "approved"
    deleted = "deleted"


class DocumentType(Base):
    """Representa un tipo documental configurable.

    Attributes:
        id: Identificador entero del tipo documental.
        name: Nombre visible del tipo documental.
        description: Descripcion funcional del documento esperado.
        is_required: Indica si el documento forma parte del paquete minimo.
        category: Categoria funcional del documento.
        is_active: Indica si el tipo documental puede usarse en cargas nuevas.
        documents: Relacion ORM con documentos asociados a este tipo.
    """

    __tablename__ = "documenttype"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    category: Mapped[DocumentCategoryEnum | None] = mapped_column(
        PGEnum(
            "Académico",
            "Administrativo",
            name="enumCategory",
            create_type=False,
        ),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    documents = relationship("Document", back_populates="document_type")


class Document(Base):
    """Representa los metadatos de un archivo documental.

    Attributes:
        id: Identificador entero del documento.
        file_name: Nombre original normalizado del archivo.
        file_path: Clave interna de storage privado.
        extension: Extension validada del archivo.
        status: Estado documental actual.
        size_bytes: Peso del archivo en bytes.
        upload_date: Fecha de carga.
        update_date: Fecha de ultima actualizacion de metadatos.
        internship_id: Practica asociada.
        type_id: Tipo documental asociado.
        user_id: Usuario propietario que cargo el documento.
        reviewed_at: Fecha de revision documental, si existe.
        reviewed_by: Usuario que reviso el documento, si existe.
        review_comment: Observacion de revision.
        deleted_at: Fecha de eliminacion logica, si existe.
        deleted_by: Usuario que elimino logicamente el documento.
    """

    __tablename__ = "document"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    extension: Mapped[DocumentExtensionEnum] = mapped_column(
        PGEnum(
            "pdf",
            "docx",
            "jpg",
            "png",
            "zip",
            name="enumExtension",
            create_type=False,
        ),
        nullable=False,
    )
    status: Mapped[DocumentStatusEnum] = mapped_column(
        PGEnum(
            "uploaded",
            "observed",
            "approved",
            "deleted",
            name="enumDocumentStatus",
            create_type=False,
        ),
        default=DocumentStatusEnum.uploaded,
        nullable=False,
    )
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    upload_date: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )
    update_date: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )
    internship_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("internship.id"),
        nullable=False,
    )
    type_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documenttype.id"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    internship = relationship("Internship")
    document_type = relationship("DocumentType", back_populates="documents")
    owner = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    deleter = relationship("User", foreign_keys=[deleted_by])
