"""Tests unitarios para el router documental."""

from datetime import date, datetime
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.documents.controllers import document_controller
from app.modules.documents.controllers.document_controller import (
    DOCUMENT_ADMIN_ROLES,
)
from app.modules.documents.services.document_service import DocumentService
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
        is_sensitive=False,
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


def _internship(user_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        user_id=user_id,
        status=SimpleNamespace(title="Pendiente"),
    )


class FakeDocumentRepository:
    def __init__(self, document=None) -> None:
        self.document = _document() if document is None else document

    async def get_document_by_id(self, document_id: int):
        if document_id == self.document.id:
            return self.document

        return None


def _config(tmp_path) -> SimpleNamespace:
    return SimpleNamespace(
        DOCUMENT_STORAGE_DIR=str(tmp_path),
        DOCUMENT_MAX_BYTES=10,
        DOCUMENT_ALLOWED_EXTENSIONS="pdf,docx,jpg,png,zip",
    )


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


class FakeUploadFile:
    filename = "formulario.pdf"

    async def read(self):
        return b"data"


class FakeDocumentService:
    def __init__(self, document=None) -> None:
        self.document = _document() if document is None else document
        self.uploaded_content = None
        self.deleted_id = None
        self.export_ids = None

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

    async def get_document_package(self, internship_id, actor):
        return SimpleNamespace(
            internship_id=internship_id,
            status="Aprobada",
            dirae_status="not_started",
            exportable=True,
            reasons=[],
            student=SimpleNamespace(
                id=10,
                rut="12.345.678-9",
                enrollment="12345678923",
                first_name="Juan",
                last_name="Perez",
                email="juan.perez@correo.cl",
                degree="Ingenieria Civil Informatica",
                cod_degree="INF-001",
            ),
            internship=SimpleNamespace(
                type="Práctica de Estudio I",
                period="Semestre",
                organization="Empresa Demo SpA",
                city="Temuco",
                start_date=date(2026, 6, 1),
                end_date=date(2026, 8, 31),
            ),
            required_documents=[
                SimpleNamespace(
                    type_id=1,
                    type_name="Formulario",
                    status="approved",
                    document=self.document,
                )
            ],
            optional_documents=[],
        )

    async def export_dirae_document_packages(self, actor, internship_ids=None):
        self.export_ids = internship_ids
        return SimpleNamespace(
            filename="dirae_document_packages_20260601_120000.csv",
            content=(
                "internship_id,student_id,student_rut,student_enrollment,"
                "student_first_name,student_last_name,student_email,"
                "degree,cod_degree,internship_type,internship_period,"
                "organization,city,start_date,end_date,"
                "approved_document_ids,required_document_type_ids,"
                "exported_at\n"
            ),
            audit_event=SimpleNamespace(
                name="dirae_export_generated",
                actor_id=99,
                internship_ids=[7],
                approved_document_ids=[55],
                filename="dirae_document_packages_20260601_120000.csv",
                result="generated",
            ),
        )


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
    assert "/internships/{internship_id}/documents/package" in paths
    assert "GET" in _methods_for_path(
        "/internships/{internship_id}/documents/package",
    )
    assert "/dirae/document-packages/export" in paths
    assert "GET" in _methods_for_path("/dirae/document-packages/export")


def test_download_document_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.get("/documents/55/download")

    assert response.status_code == 401


def test_download_document_returns_file_for_owner(monkeypatch, tmp_path) -> None:
    document = _document()
    document.file_path = "7/formulario.pdf"
    document.internship = _internship(user_id=10)
    stored_file = tmp_path / document.file_path
    stored_file.parent.mkdir(parents=True)
    stored_file.write_bytes(b"private-data")
    repository = FakeDocumentRepository(document=document)
    service = DocumentService(
        document_repository=repository,
        app_config=_config(tmp_path),
    )
    monkeypatch.setattr(
        document_controller,
        "_build_service",
        lambda db: service,
    )
    app.dependency_overrides[document_controller.get_current_user] = lambda: _user(
        10,
        ["Estudiante"],
    )
    app.dependency_overrides[document_controller.get_db] = lambda: object()

    with TestClient(app) as client:
        response = client.get("/documents/55/download")

    assert response.status_code == 200
    assert response.content == b"private-data"
    assert "formulario.pdf" in response.headers["content-disposition"]


def test_download_document_rejects_cross_student(monkeypatch, tmp_path) -> None:
    document = _document()
    document.file_path = "7/formulario.pdf"
    document.internship = _internship(user_id=10)
    stored_file = tmp_path / document.file_path
    stored_file.parent.mkdir(parents=True)
    stored_file.write_bytes(b"private-data")
    repository = FakeDocumentRepository(document=document)
    service = DocumentService(
        document_repository=repository,
        app_config=_config(tmp_path),
    )
    monkeypatch.setattr(
        document_controller,
        "_build_service",
        lambda db: service,
    )
    app.dependency_overrides[document_controller.get_current_user] = lambda: _user(
        99,
        ["Estudiante"],
    )
    app.dependency_overrides[document_controller.get_db] = lambda: object()

    with TestClient(app) as client:
        response = client.get("/documents/55/download")

    assert response.status_code == 403


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
@pytest.mark.parametrize("role", ["Estudiante", "FICA"])
async def test_update_document_status_rejects_non_document_admin_roles(
    role: str,
) -> None:
    role_checker = require_roles(DOCUMENT_ADMIN_ROLES)

    with pytest.raises(HTTPException) as exc:
        await role_checker(_user(10, [role]))

    assert exc.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["Estudiante", "FICA"])
async def test_export_dirae_document_packages_rejects_non_document_admin_roles(
    role: str,
) -> None:
    role_checker = require_roles(DOCUMENT_ADMIN_ROLES)

    with pytest.raises(HTTPException) as exc:
        await role_checker(_user(10, [role]))

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
async def test_get_document_package_returns_summary(monkeypatch):
    service = FakeDocumentService()
    monkeypatch.setattr(
        document_controller,
        "_build_service",
        lambda db: service,
    )

    result = await document_controller.get_document_package(
        internship_id=7,
        db=object(),
        current_user=_user(10, ["Estudiante"]),
    )

    assert result.internship_id == 7
    assert result.exportable is True
    assert result.required_documents[0].document.id == 55


@pytest.mark.asyncio
async def test_export_dirae_document_packages_returns_csv(monkeypatch):
    service = FakeDocumentService()
    monkeypatch.setattr(
        document_controller,
        "_build_service",
        lambda db: service,
    )

    response = await document_controller.export_dirae_document_packages(
        db=object(),
        current_user=_user(99, ["Secretaria de Carrera"]),
        internship_ids=[7],
    )

    assert response.media_type == "text/csv; charset=utf-8"
    assert service.export_ids == [7]
    assert b"internship_id,student_id" in response.body
    assert response.headers["Content-Disposition"].endswith(".csv\"")


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
