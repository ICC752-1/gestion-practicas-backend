"""Schemas Pydantic del modulo de documentos."""

from app.modules.documents.schemas.document_schema import (
    DocumentPackageInternshipResponse,
    DocumentPackageItemResponse,
    DocumentPackageResponse,
    DocumentPackageStudentResponse,
    DocumentResponse,
    DocumentStatusUpdateRequest,
    DocumentTypeResponse,
)

__all__ = [
    "DocumentPackageInternshipResponse",
    "DocumentPackageItemResponse",
    "DocumentPackageResponse",
    "DocumentPackageStudentResponse",
    "DocumentResponse",
    "DocumentStatusUpdateRequest",
    "DocumentTypeResponse",
]
