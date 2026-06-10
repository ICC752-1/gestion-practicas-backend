"""Schemas Pydantic del modulo de documentos."""

from app.modules.documents.schemas.document_schema import (
    DocumentResponse,
    DocumentStatusUpdateRequest,
    DocumentTypeResponse,
)

__all__ = [
    "DocumentResponse",
    "DocumentStatusUpdateRequest",
    "DocumentTypeResponse",
]
