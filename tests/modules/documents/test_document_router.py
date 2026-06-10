"""Tests unitarios para el router documental."""

from datetime import datetime
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.main import app
from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.documents.controllers import document_controller
from app.modules.documents.controllers.document_controller import (
    DOCUMENT_ADMIN_ROLES,
)
from app.modules.documents.models.document_model import (
    DocumentCategoryEnum,
    DocumentExtensionEnum,
    DocumentStatusEnum,
)


def _methods_for_path(path: str) -> set[str]:
    methods: set[str] = set()

    for route in app.routes:
        if route.path == path and hasattr(route, "methods"):
            methods.update(route.methods)

    return methods


def _role(name: str) -> SimpleNamespace:
    return SimpleNamespace(role=SimpleNamespace(name=name))


def _user(user_id: int, roles: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        roles=[_role(role_name) for role_name in roles],
    )


def _document_type() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        name="Formulario",
        description="Formulario de inscripción",
        is_required=True,
        category=DocumentCategoryEnum.academic,
        is_active=True,
    )


def _document(status: DocumentStatusEnum = DocumentStatusEnum.uploaded):
    document_type = _document_type()

    return SimpleNamespace(
        id=55,
        file_name="formulario.pdf",
        extension=DocumentExtensionEnum.pdf,
        status=status,
        size_bytes=4,
        upload_date=datetime(2026, 6, 1, 9, 0, 0),
        update_date=datetime(2026, 6, 1, 9, 0, 0),
        internship_id=7,
        type_id=document_type.id,
        user_id=10,
        reviewed_at=None,
        reviewed_by=None,
        review_comment=None,
        deleted_at=None,
        deleted_by=None,
        document_type=document_type,
    )


class FakeUploadFile:
    filename = "formulario.pdf"

    async def read(self):
        return b"data"


class FakeDocumentService:
    def __init__(self, document=None) -> None:
        self.document = _document() if document is None else document
        self.uploaded_content = None
        self.deleted_id = None

    async def list_document_types(self):
        return [_document_type()]

    async def upload_document(
        self,
        internship_id,
        document_type_id,
        file_name,
        content,
        actor,
    ):
        self.uploaded_content = content
        return self.document

    async def list_internship_documents(self, internship_id, actor):
        return [self.document]

    async def update_document_status(
        self,
        document_id,
        new_status,
        comment,
        actor,
    ):
        self.document.status = new_status
        self.document.review_comment = comment
        return self.document

    async def soft_delete_document(self, document_id, actor):
        self.deleted_id = document_id
        return self.document


def test_documents_router_is_registered() -> None:
    paths = {route.path for route in app.routes}

    assert "/documents/types" in paths
    assert "GET" in _methods_for_path("/documents/types")
    assert "/internships/{internship_id}/documents" in paths
    assert "POST" in _methods_for_path("/internships/{internship_id}/documents")
    assert "GET" in _methods_for_path("/internships/{internship_id}/documents")
    assert "/documents/{document_id}/download" in paths
    assert "GET" in _methods_for_path("/documents/{document_id}/download")
    assert "/documents/{document_id}/status" in paths
    assert "PATCH" in _methods_for_path("/documents/{document_id}/status")
    assert "/documents/{document_id}" in paths
    assert "DELETE" in _methods_for_path("/documents/{document_id}")


@pytest.mark.asyncio
async def test_list_document_types_returns_active_types(monkeypatch):
    service = FakeDocumentService()
    monkeypatch.setattr(
        document_controller,
        "_build_service",
        lambda db: service,
    )

    result = await document_controller.list_document_types(
        db=object(),
        current_user=_user(10, ["Estudiante"]),
    )

    assert len(result) == 1
    assert result[0].id == 1


@pytest.mark.asyncio
async def test_upload_document_reads_file_and_returns_metadata(monkeypatch):
    service = FakeDocumentService()
    monkeypatch.setattr(
        document_controller,
        "_build_service",
        lambda db: service,
    )

    result = await document_controller.upload_document(
        internship_id=7,
        db=object(),
        current_user=_user(10, ["Estudiante"]),
        document_type_id=1,
        file=FakeUploadFile(),
    )

    assert result.id == 55
    assert service.uploaded_content == b"data"


@pytest.mark.asyncio
async def test_update_document_status_rejects_student_role() -> None:
    role_checker = require_roles(DOCUMENT_ADMIN_ROLES)

    with pytest.raises(HTTPException) as exc:
        await role_checker(_user(10, ["Estudiante"]))

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_update_document_status_returns_reviewed_document(monkeypatch):
    service = FakeDocumentService()
    monkeypatch.setattr(
        document_controller,
        "_build_service",
        lambda db: service,
    )

    payload = document_controller.DocumentStatusUpdateRequest(
        status="observed",
        comment="Falta firma",
    )
    result = await document_controller.update_document_status(
        document_id=55,
        payload=payload,
        db=object(),
        current_user=_user(99, ["Secretaria de Carrera"]),
    )

    assert result.status == DocumentStatusEnum.observed
    assert result.review_comment == "Falta firma"


@pytest.mark.asyncio
async def test_delete_document_returns_204(monkeypatch):
    service = FakeDocumentService()
    monkeypatch.setattr(
        document_controller,
        "_build_service",
        lambda db: service,
    )

    response = await document_controller.delete_document(
        document_id=55,
        db=object(),
        current_user=_user(10, ["Estudiante"]),
    )

    assert response.status_code == 204
    assert service.deleted_id == 55


@pytest.mark.asyncio
async def test_router_propagates_service_errors(monkeypatch):
    class ErrorService(FakeDocumentService):
        async def list_internship_documents(self, internship_id, actor):
            raise HTTPException(status_code=404, detail="Internship not found")

    monkeypatch.setattr(
        document_controller,
        "_build_service",
        lambda db: ErrorService(),
    )

    with pytest.raises(HTTPException) as exc:
        await document_controller.list_internship_documents(
            internship_id=404,
            db=object(),
            current_user=_user(10, ["Estudiante"]),
        )

    assert exc.value.status_code == 404


def test_fake_upload_file_shape_matches_needed_api() -> None:
    upload = FakeUploadFile()

    assert upload.filename == "formulario.pdf"
    assert isinstance(BytesIO(b"data"), BytesIO)
