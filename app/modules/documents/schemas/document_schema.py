"""Schemas Pydantic para contratos HTTP de documentos."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.documents.models.document_model import (
    DocumentCategoryEnum,
    DocumentExtensionEnum,
    DocumentStatusEnum,
)


class DocumentTypeResponse(BaseModel):
    """Respuesta con un tipo documental activo.

    Attributes:
        id: Identificador del tipo documental.
        name: Nombre visible.
        description: Descripcion funcional.
        is_required: Indica si es parte del paquete minimo.
        category: Categoria funcional.
        is_active: Indica si puede usarse en cargas nuevas.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    is_required: bool
    category: DocumentCategoryEnum | None
    is_active: bool


class DocumentResponse(BaseModel):
    """Respuesta publica de metadatos documentales.

    No incluye `file_path` porque es una clave interna de storage privado.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    extension: DocumentExtensionEnum
    status: DocumentStatusEnum
    size_bytes: int
    upload_date: datetime
    update_date: datetime
    internship_id: int
    type_id: int
    user_id: int
    reviewed_at: datetime | None
    reviewed_by: int | None
    review_comment: str | None
    deleted_at: datetime | None
    deleted_by: int | None
    document_type: DocumentTypeResponse | None = None


class DocumentStatusUpdateRequest(BaseModel):
    """Payload para observar o aprobar un documento.

    Attributes:
        status: Estado documental destino permitido.
        comment: Observacion de revision; obligatoria para `observed`.
    """

    status: Literal["observed", "approved"]
    comment: str | None = Field(default=None, max_length=1000)


class DocumentPackageStudentResponse(BaseModel):
    """Datos del estudiante incluidos en un paquete documental."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None
    rut: str | None
    enrollment: str | None
    first_name: str | None
    last_name: str | None
    email: str | None
    degree: str | None
    cod_degree: str | None


class DocumentPackageInternshipResponse(BaseModel):
    """Datos de la practica incluidos en un paquete documental."""

    model_config = ConfigDict(from_attributes=True)

    type: str | None
    period: str | None
    organization: str | None
    city: str | None
    start_date: date | None
    end_date: date | None


class DocumentPackageItemResponse(BaseModel):
    """Estado de un tipo documental dentro del paquete."""

    model_config = ConfigDict(from_attributes=True)

    type_id: int
    type_name: str
    status: Literal["approved", "missing"]
    document: DocumentResponse | None


class DocumentPackageResponse(BaseModel):
    """Resumen documental exportable a DIRAE."""

    model_config = ConfigDict(from_attributes=True)

    internship_id: int
    status: str | None
    exportable: bool
    reasons: list[
        Literal["internship_not_approved", "missing_required_documents"]
    ]
    student: DocumentPackageStudentResponse
    internship: DocumentPackageInternshipResponse
    required_documents: list[DocumentPackageItemResponse]
    optional_documents: list[DocumentPackageItemResponse]
