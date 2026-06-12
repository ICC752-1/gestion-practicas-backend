"""Tests unitarios para el servicio documental."""

from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.documents.models.document_model import (
    DocumentCategoryEnum,
    DocumentExtensionEnum,
    DocumentStatusEnum,
)
from app.modules.documents.services.document_service import DocumentService


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.document_types = {
            1: _document_type(1),
        }
        self.internship_by_id = _internship(user_id=10)
        self.documents_by_id = {}
        self.listed_documents = []
        self.created_document = None
        self.updated_document = None
        self.deleted_document = None

    async def list_active_document_types(self):
        return list(self.document_types.values())

    async def get_document_type_by_id(self, document_type_id: int):
        return self.document_types.get(document_type_id)

    async def get_internship_by_id(self, internship_id: int):
        return self.internship_by_id

    async def create_document(self, document):
        document.id = 100
        self.created_document = document
        self.documents_by_id[document.id] = document

        return document

    async def list_documents_by_internship(self, internship_id: int):
        return self.listed_documents

    async def get_document_by_id(self, document_id: int):
        return self.documents_by_id.get(document_id)

    async def update_document_status(
        self,
        document,
        new_status,
        reviewer_id,
        comment,
    ):
        document.status = new_status
        document.reviewed_by = reviewer_id
        document.review_comment = comment
        document.reviewed_at = datetime(2026, 6, 1, 10, 0, 0)
        self.updated_document = document

        return document

    async def soft_delete_document(self, document, actor_id):
        document.status = DocumentStatusEnum.deleted
        document.deleted_by = actor_id
        document.deleted_at = datetime(2026, 6, 1, 10, 0, 0)
        self.deleted_document = document

        return document


def _config(tmp_path, max_bytes: int = 10) -> SimpleNamespace:
    return SimpleNamespace(
        DOCUMENT_STORAGE_DIR=str(tmp_path),
        DOCUMENT_MAX_BYTES=max_bytes,
        DOCUMENT_ALLOWED_EXTENSIONS="pdf,docx,jpg,png,zip",
    )


def _role(name: str) -> SimpleNamespace:
    return SimpleNamespace(role=SimpleNamespace(name=name))


def _user(user_id: int, *roles: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        roles=[_role(role_name) for role_name in roles],
    )


def _status(title: str) -> SimpleNamespace:
    return SimpleNamespace(title=title)


def _internship(
    user_id: int,
    status_title: str = "Pendiente",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        user_id=user_id,
        status=_status(status_title),
    )


def _document_type(document_type_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=document_type_id,
        name="Formulario",
        description="Formulario de inscripción",
        is_required=True,
        category=DocumentCategoryEnum.academic,
        is_active=True,
    )


def _document(
    user_id: int = 10,
    status: DocumentStatusEnum = DocumentStatusEnum.uploaded,
    internship=None,
    file_path: str = "7/test.pdf",
) -> SimpleNamespace:
    if internship is None:
        internship = _internship(user_id=user_id)

    return SimpleNamespace(
        id=55,
        file_name="formulario.pdf",
        file_path=file_path,
        extension=DocumentExtensionEnum.pdf,
        status=status,
        size_bytes=4,
        upload_date=datetime(2026, 6, 1, 9, 0, 0),
        update_date=datetime(2026, 6, 1, 9, 0, 0),
        internship_id=internship.id,
        type_id=1,
        user_id=user_id,
        reviewed_at=None,
        reviewed_by=None,
        review_comment=None,
        deleted_at=None,
        deleted_by=None,
        internship=internship,
        document_type=_document_type(1),
    )


def _service(tmp_path, repository=None, max_bytes: int = 10) -> DocumentService:
    if repository is None:
        repository = FakeDocumentRepository()

    return DocumentService(
        document_repository=repository,
        app_config=_config(tmp_path, max_bytes=max_bytes),
    )


@pytest.mark.asyncio
async def test_upload_document_validates_and_persists_metadata(tmp_path):
    repository = FakeDocumentRepository()
    service = _service(tmp_path, repository=repository)
    actor = _user(10, "Estudiante")

    document = await service.upload_document(
        internship_id=7,
        document_type_id=1,
        file_name="formulario.pdf",
        content=b"data",
        actor=actor,
    )

    assert document is repository.created_document
    assert document.id == 100
    assert document.user_id == 10
    assert document.internship_id == 7
    assert document.type_id == 1
    assert document.status == DocumentStatusEnum.uploaded
    assert document.size_bytes == 4
    assert document.file_path.startswith("7/")
    assert (tmp_path / document.file_path).read_bytes() == b"data"


@pytest.mark.asyncio
async def test_upload_rejects_invalid_extension(tmp_path):
    service = _service(tmp_path)

    with pytest.raises(HTTPException) as exc:
        await service.upload_document(
            internship_id=7,
            document_type_id=1,
            file_name="script.exe",
            content=b"data",
            actor=_user(10, "Estudiante"),
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_upload_rejects_size_over_limit(tmp_path):
    service = _service(tmp_path, max_bytes=3)

    with pytest.raises(HTTPException) as exc:
        await service.upload_document(
            internship_id=7,
            document_type_id=1,
            file_name="formulario.pdf",
            content=b"data",
            actor=_user(10, "Estudiante"),
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_upload_rejects_missing_document_type(tmp_path):
    service = _service(tmp_path)

    with pytest.raises(HTTPException) as exc:
        await service.upload_document(
            internship_id=7,
            document_type_id=999,
            file_name="formulario.pdf",
            content=b"data",
            actor=_user(10, "Estudiante"),
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_upload_rejects_missing_internship(tmp_path):
    repository = FakeDocumentRepository()
    repository.internship_by_id = None
    service = _service(tmp_path, repository=repository)

    with pytest.raises(HTTPException) as exc:
        await service.upload_document(
            internship_id=404,
            document_type_id=1,
            file_name="formulario.pdf",
            content=b"data",
            actor=_user(10, "Estudiante"),
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_upload_rejects_non_owner_student(tmp_path):
    service = _service(tmp_path)

    with pytest.raises(HTTPException) as exc:
        await service.upload_document(
            internship_id=7,
            document_type_id=1,
            file_name="formulario.pdf",
            content=b"data",
            actor=_user(99, "Estudiante"),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_upload_rejects_terminal_internship(tmp_path):
    repository = FakeDocumentRepository()
    repository.internship_by_id = _internship(
        user_id=10,
        status_title="Aprobada",
    )
    service = _service(tmp_path, repository=repository)

    with pytest.raises(HTTPException) as exc:
        await service.upload_document(
            internship_id=7,
            document_type_id=1,
            file_name="formulario.pdf",
            content=b"data",
            actor=_user(10, "Estudiante"),
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_list_documents_allows_owner_and_admin(tmp_path):
    repository = FakeDocumentRepository()
    repository.listed_documents = [_document(user_id=10)]
    service = _service(tmp_path, repository=repository)

    owner_result = await service.list_internship_documents(
        internship_id=7,
        actor=_user(10, "Estudiante"),
    )
    admin_result = await service.list_internship_documents(
        internship_id=7,
        actor=_user(99, "Secretaria de Carrera"),
    )

    assert owner_result == repository.listed_documents
    assert admin_result == repository.listed_documents


@pytest.mark.asyncio
async def test_list_documents_rejects_cross_access(tmp_path):
    service = _service(tmp_path)

    with pytest.raises(HTTPException) as exc:
        await service.list_internship_documents(
            internship_id=7,
            actor=_user(99, "Estudiante"),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_download_allows_owner_and_rejects_cross_access(tmp_path):
    repository = FakeDocumentRepository()
    document = _document(user_id=10)
    (tmp_path / document.file_path).parent.mkdir(parents=True)
    (tmp_path / document.file_path).write_bytes(b"data")
    repository.documents_by_id[document.id] = document
    service = _service(tmp_path, repository=repository)

    download = await service.prepare_download(
        document_id=document.id,
        actor=_user(10, "Estudiante"),
    )

    assert download.path == tmp_path / document.file_path

    with pytest.raises(HTTPException) as exc:
        await service.prepare_download(
            document_id=document.id,
            actor=_user(99, "Estudiante"),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_download_rejects_missing_file(tmp_path):
    repository = FakeDocumentRepository()
    document = _document(user_id=10)
    repository.documents_by_id[document.id] = document
    service = _service(tmp_path, repository=repository)

    with pytest.raises(HTTPException) as exc:
        await service.prepare_download(
            document_id=document.id,
            actor=_user(10, "Estudiante"),
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_download_rejects_deleted_document(tmp_path):
    repository = FakeDocumentRepository()
    document = _document(
        user_id=10,
        status=DocumentStatusEnum.deleted,
    )
    document.deleted_at = datetime(2026, 6, 1, 10, 0, 0)
    repository.documents_by_id[document.id] = document
    service = _service(tmp_path, repository=repository)

    with pytest.raises(HTTPException) as exc:
        await service.prepare_download(
            document_id=document.id,
            actor=_user(10, "Estudiante"),
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_observed_status_requires_comment(tmp_path):
    repository = FakeDocumentRepository()
    repository.documents_by_id[55] = _document()
    service = _service(tmp_path, repository=repository)

    with pytest.raises(HTTPException) as exc:
        await service.update_document_status(
            document_id=55,
            new_status=DocumentStatusEnum.observed,
            comment=" ",
            actor=_user(99, "Secretaria de Carrera"),
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_observed_status_with_comment_updates_document(tmp_path):
    repository = FakeDocumentRepository()
    repository.documents_by_id[55] = _document()
    service = _service(tmp_path, repository=repository)

    document = await service.update_document_status(
        document_id=55,
        new_status=DocumentStatusEnum.observed,
        comment="Falta firma",
        actor=_user(99, "Secretaria de Carrera"),
    )

    assert document.status == DocumentStatusEnum.observed
    assert document.reviewed_by == 99
    assert document.review_comment == "Falta firma"


@pytest.mark.asyncio
async def test_approved_status_updates_document(tmp_path):
    repository = FakeDocumentRepository()
    repository.documents_by_id[55] = _document()
    service = _service(tmp_path, repository=repository)

    document = await service.update_document_status(
        document_id=55,
        new_status=DocumentStatusEnum.approved,
        comment=None,
        actor=_user(99, "Director de carrera"),
    )

    assert document.status == DocumentStatusEnum.approved
    assert document.reviewed_by == 99


@pytest.mark.asyncio
async def test_student_cannot_delete_approved_document(tmp_path):
    repository = FakeDocumentRepository()
    repository.documents_by_id[55] = _document(
        status=DocumentStatusEnum.approved,
    )
    service = _service(tmp_path, repository=repository)

    with pytest.raises(HTTPException) as exc:
        await service.soft_delete_document(
            document_id=55,
            actor=_user(10, "Estudiante"),
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_admin_can_soft_delete_approved_document(tmp_path):
    repository = FakeDocumentRepository()
    repository.documents_by_id[55] = _document(
        status=DocumentStatusEnum.approved,
    )
    service = _service(tmp_path, repository=repository)

    document = await service.soft_delete_document(
        document_id=55,
        actor=_user(99, "Encargado de practica"),
    )

    assert document.status == DocumentStatusEnum.deleted
    assert document.deleted_by == 99
