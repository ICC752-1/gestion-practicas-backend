"""Tests de contrato para modelos documentales."""

from app.modules.documents.models.document_model import (
    Document,
    DocumentStatusEnum,
    DocumentType,
)


def test_document_model_matches_database_contract() -> None:
    columns = Document.__table__.c

    assert Document.__tablename__ == "document"
    assert "file_name" in columns
    assert "file_path" in columns
    assert "extension" in columns
    assert "status" in columns
    assert "size_bytes" in columns
    assert "reviewed_at" in columns
    assert "reviewed_by" in columns
    assert "review_comment" in columns
    assert "deleted_at" in columns
    assert "deleted_by" in columns


def test_document_status_enum_matches_business_contract() -> None:
    values = {status.value for status in DocumentStatusEnum}

    assert values == {"uploaded", "observed", "approved", "deleted"}


def test_document_type_model_includes_active_flag() -> None:
    columns = DocumentType.__table__.c

    assert DocumentType.__tablename__ == "documenttype"
    assert "is_active" in columns
