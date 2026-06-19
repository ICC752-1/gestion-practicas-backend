"""Tests unitarios para el servicio documental."""

from csv import DictReader
from datetime import date, datetime
from io import StringIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.documents.models.document_model import (
    DocumentCategoryEnum,
    DocumentExtensionEnum,
    DocumentStatusEnum,
)
from app.modules.documents.services.document_service import DocumentService
from app.modules.internships.models.internship_model import (
    CompletionStatusEnum,
    DiraeStatusEnum,
)


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.document_types = {
            1: _document_type(1),
        }
        self.internship_by_id = _internship(user_id=10)
        self.documents_by_id = {}
        self.listed_documents = []
        self.package_documents = []
        self.required_document_types = [self.document_types[1]]
        self.export_internships = [self.internship_by_id]
        self.created_document = None
        self.updated_document = None
        self.deleted_document = None
        self.exported_internships = []
        self.export_actor_id = None
        self.export_reason = None

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

    async def list_required_document_types(self):
        return self.required_document_types

    async def list_package_documents_by_internship(self, internship_id: int):
        return [
            document
            for document in self.package_documents
            if document.internship_id == internship_id
        ]

    async def list_internships_for_dirae_export(
        self,
        internship_ids: list[int] | None = None,
    ):
        if internship_ids is None:
            return self.export_internships

        return [
            internship
            for internship in self.export_internships
            if internship.id in internship_ids
        ]

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

    async def mark_internships_as_dirae_exported(
        self,
        internships,
        actor_id,
        reason,
    ):
        self.exported_internships = internships
        self.export_actor_id = actor_id
        self.export_reason = reason
        for internship in internships:
            internship.dirae_status = DiraeStatusEnum.exported


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


def _student(user_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        rut="12.345.678-9",
        first_name="Juan",
        last_name="Perez",
        email="juan.perez@correo.cl",
        degree="Ingenieria Civil Informatica",
        cod_degree="INF-001",
    )


def _internship(
    user_id: int,
    status_title: str = "Pendiente",
    completion_status: CompletionStatusEnum = CompletionStatusEnum.not_started,
    dirae_status: DiraeStatusEnum = DiraeStatusEnum.not_started,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        user_id=user_id,
        status=_status(status_title),
        completion_status=completion_status,
        dirae_status=dirae_status,
        student=_student(user_id),
        org_name="Empresa Demo SpA",
        city="Temuco",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 8, 31),
        internship_period="Semestre",
        internship_type="Práctica de Estudio I",
    )


def _document_type(
    document_type_id: int,
    *,
    is_required: bool = True,
    name: str = "Formulario",
    is_sensitive: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=document_type_id,
        name=name,
        description="Formulario de inscripción",
        is_required=is_required,
        category=DocumentCategoryEnum.academic,
        is_sensitive=is_sensitive,
        is_active=True,
    )


def _document(
    user_id: int = 10,
    status: DocumentStatusEnum = DocumentStatusEnum.uploaded,
    internship=None,
    file_path: str = "7/test.pdf",
    document_id: int = 55,
    document_type=None,
    upload_date: datetime | None = None,
    deleted_at: datetime | None = None,
) -> SimpleNamespace:
    if internship is None:
        internship = _internship(user_id=user_id)
    if document_type is None:
        document_type = _document_type(1)

    return SimpleNamespace(
        id=document_id,
        file_name="formulario.pdf",
        file_path=file_path,
        extension=DocumentExtensionEnum.pdf,
        status=status,
        size_bytes=4,
        upload_date=upload_date or datetime(2026, 6, 1, 9, 0, 0),
        update_date=datetime(2026, 6, 1, 9, 0, 0),
        internship_id=internship.id,
        type_id=document_type.id,
        user_id=user_id,
        reviewed_at=None,
        reviewed_by=None,
        review_comment=None,
        deleted_at=deleted_at,
        deleted_by=None,
        internship=internship,
        document_type=document_type,
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
async def test_list_documents_filters_sensitive_documents_for_secretary(tmp_path):
    repository = FakeDocumentRepository()
    public_document = _document(
        document_id=55,
        document_type=_document_type(1, name="Formulario"),
    )
    sensitive_document = _document(
        document_id=56,
        document_type=_document_type(
            2,
            name="Seguro escolar",
            is_sensitive=True,
        ),
    )
    repository.listed_documents = [public_document, sensitive_document]
    service = _service(tmp_path, repository=repository)

    documents = await service.list_internship_documents(
        internship_id=7,
        actor=_admin_user(),
    )

    assert documents == [public_document]


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
async def test_list_documents_rejects_fica_role(tmp_path):
    service = _service(tmp_path)

    with pytest.raises(HTTPException) as exc:
        await service.list_internship_documents(
            internship_id=7,
            actor=_user(99, "FICA"),
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
async def test_download_rejects_fica_role(tmp_path):
    repository = FakeDocumentRepository()
    document = _document(user_id=10)
    (tmp_path / document.file_path).parent.mkdir(parents=True)
    (tmp_path / document.file_path).write_bytes(b"data")
    repository.documents_by_id[document.id] = document
    service = _service(tmp_path, repository=repository)

    with pytest.raises(HTTPException) as exc:
        await service.prepare_download(
            document_id=document.id,
            actor=_user(99, "FICA"),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_download_rejects_sensitive_document_for_secretary(tmp_path):
    repository = FakeDocumentRepository()
    document = _document(
        user_id=10,
        document_type=_document_type(
            2,
            name="Seguro escolar",
            is_sensitive=True,
        ),
    )
    repository.documents_by_id[document.id] = document
    service = _service(tmp_path, repository=repository)

    with pytest.raises(HTTPException) as exc:
        await service.prepare_download(
            document_id=document.id,
            actor=_admin_user(),
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


def _package_repository(
    *,
    status_title: str = "Aprobada",
    completion_status: CompletionStatusEnum = CompletionStatusEnum.finalized,
    dirae_status: DiraeStatusEnum = DiraeStatusEnum.ready,
    documents: list[SimpleNamespace] | None = None,
    required_types: list[SimpleNamespace] | None = None,
) -> FakeDocumentRepository:
    repository = FakeDocumentRepository()
    repository.internship_by_id = _internship(
        user_id=10,
        status_title=status_title,
        completion_status=completion_status,
        dirae_status=dirae_status,
    )
    if required_types is None:
        required_types = [
            _document_type(1, name="Formulario de inscripción"),
        ]
    repository.required_document_types = required_types
    repository.export_internships = [repository.internship_by_id]
    if documents is None:
        documents = [
            _document(
                status=DocumentStatusEnum.approved,
                internship=repository.internship_by_id,
                document_type=required_types[0],
            )
        ]
    repository.package_documents = documents

    return repository


def _admin_user() -> SimpleNamespace:
    return _user(99, "Secretaria de Carrera")


@pytest.mark.asyncio
async def test_package_is_exportable_with_approved_internship_and_docs(tmp_path):
    repository = _package_repository()
    service = _service(tmp_path, repository=repository)

    package = await service.get_document_package(
        internship_id=7,
        actor=_user(10, "Estudiante"),
    )

    assert package.exportable is True
    assert package.reasons == []
    assert package.status == "Aprobada"
    assert package.required_documents[0].status == "approved"
    assert package.required_documents[0].document.id == 55


@pytest.mark.asyncio
async def test_package_builds_student_enrollment_when_year_is_available(
    tmp_path,
):
    repository = _package_repository()
    repository.internship_by_id.student.admission_year = 2023
    service = _service(tmp_path, repository=repository)

    package = await service.get_document_package(
        internship_id=7,
        actor=_user(10, "Estudiante"),
    )

    assert package.student.enrollment == "12345678923"


@pytest.mark.asyncio
async def test_package_keeps_student_enrollment_empty_without_year(tmp_path):
    repository = _package_repository()
    service = _service(tmp_path, repository=repository)

    package = await service.get_document_package(
        internship_id=7,
        actor=_user(10, "Estudiante"),
    )

    assert package.student.enrollment is None


@pytest.mark.asyncio
async def test_package_not_exportable_when_internship_is_not_approved(tmp_path):
    repository = _package_repository(status_title="Pendiente")
    service = _service(tmp_path, repository=repository)

    package = await service.get_document_package(
        internship_id=7,
        actor=_user(10, "Estudiante"),
    )

    assert package.exportable is False
    assert package.reasons == ["internship_not_approved"]


@pytest.mark.asyncio
async def test_package_not_exportable_when_practice_is_not_finalized(tmp_path):
    repository = _package_repository(
        completion_status=CompletionStatusEnum.pending_evaluations,
    )
    service = _service(tmp_path, repository=repository)

    package = await service.get_document_package(
        internship_id=7,
        actor=_user(10, "Estudiante"),
    )

    assert package.exportable is False
    assert package.reasons == ["practice_not_finalized"]


@pytest.mark.asyncio
async def test_package_not_exportable_when_dirae_status_is_not_ready(tmp_path):
    repository = _package_repository(
        dirae_status=DiraeStatusEnum.in_review,
    )
    service = _service(tmp_path, repository=repository)

    package = await service.get_document_package(
        internship_id=7,
        actor=_user(10, "Estudiante"),
    )

    assert package.exportable is False
    assert package.reasons == ["dirae_not_ready"]


@pytest.mark.asyncio
async def test_package_not_exportable_when_required_document_missing(tmp_path):
    repository = _package_repository(documents=[])
    service = _service(tmp_path, repository=repository)

    package = await service.get_document_package(
        internship_id=7,
        actor=_user(10, "Estudiante"),
    )

    assert package.exportable is False
    assert package.reasons == ["missing_required_documents"]
    assert package.required_documents[0].status == "missing"
    assert package.required_documents[0].document is None


@pytest.mark.asyncio
async def test_package_not_exportable_when_observed_documents_are_pending(tmp_path):
    repository = _package_repository()
    document_type = repository.required_document_types[0]
    approved = _document(
        status=DocumentStatusEnum.approved,
        internship=repository.internship_by_id,
        document_id=55,
        document_type=document_type,
    )
    observed = _document(
        status=DocumentStatusEnum.observed,
        internship=repository.internship_by_id,
        document_id=56,
        document_type=document_type,
    )
    repository.package_documents = [approved, observed]
    service = _service(tmp_path, repository=repository)

    package = await service.get_document_package(
        internship_id=7,
        actor=_admin_user(),
    )

    assert package.exportable is False
    assert package.reasons == ["observed_documents_pending"]


@pytest.mark.asyncio
async def test_package_filters_sensitive_documents_for_secretary(tmp_path):
    repository = _package_repository()
    public_type = repository.required_document_types[0]
    sensitive_type = _document_type(
        2,
        is_required=False,
        name="Seguro escolar",
        is_sensitive=True,
    )
    public_document = _document(
        status=DocumentStatusEnum.approved,
        internship=repository.internship_by_id,
        document_id=55,
        document_type=public_type,
    )
    sensitive_document = _document(
        status=DocumentStatusEnum.approved,
        internship=repository.internship_by_id,
        document_id=56,
        document_type=sensitive_type,
    )
    repository.package_documents = [public_document, sensitive_document]
    service = _service(tmp_path, repository=repository)

    package = await service.get_document_package(
        internship_id=7,
        actor=_admin_user(),
    )

    assert package.exportable is False
    assert package.reasons == ["sensitive_document_restricted"]
    assert package.required_documents[0].document == public_document
    assert package.optional_documents == []


@pytest.mark.asyncio
async def test_package_allows_sensitive_documents_for_director(tmp_path):
    repository = _package_repository()
    sensitive_type = _document_type(
        2,
        is_required=False,
        name="Seguro escolar",
        is_sensitive=True,
    )
    sensitive_document = _document(
        status=DocumentStatusEnum.approved,
        internship=repository.internship_by_id,
        document_id=56,
        document_type=sensitive_type,
    )
    repository.package_documents.append(sensitive_document)
    service = _service(tmp_path, repository=repository)

    package = await service.get_document_package(
        internship_id=7,
        actor=_user(99, "Director de carrera"),
    )

    assert package.exportable is True
    assert package.reasons == []
    assert package.optional_documents[0].document == sensitive_document


@pytest.mark.asyncio
async def test_package_requires_all_required_document_types(tmp_path):
    required_types = [
        _document_type(1, name="Formulario de inscripción"),
        _document_type(2, name="Carta de aceptación"),
    ]
    repository = _package_repository(required_types=required_types)
    repository.package_documents = [
        _document(
            status=DocumentStatusEnum.approved,
            internship=repository.internship_by_id,
            document_type=required_types[0],
        )
    ]
    service = _service(tmp_path, repository=repository)

    package = await service.get_document_package(
        internship_id=7,
        actor=_admin_user(),
    )

    assert package.exportable is False
    assert package.reasons == ["missing_required_documents"]
    assert package.required_documents[0].status == "approved"
    assert package.required_documents[1].status == "missing"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("document_status", "expected_reasons"),
    [
        (DocumentStatusEnum.uploaded, ["missing_required_documents"]),
        (
            DocumentStatusEnum.observed,
            ["missing_required_documents", "observed_documents_pending"],
        ),
    ],
)
async def test_package_ignores_non_approved_documents(
    tmp_path,
    document_status,
    expected_reasons,
):
    repository = _package_repository()
    repository.package_documents = [
        _document(
            status=document_status,
            internship=repository.internship_by_id,
            document_type=repository.required_document_types[0],
        )
    ]
    service = _service(tmp_path, repository=repository)

    package = await service.get_document_package(
        internship_id=7,
        actor=_admin_user(),
    )

    assert package.exportable is False
    assert package.reasons == expected_reasons


@pytest.mark.asyncio
async def test_package_ignores_deleted_document(tmp_path):
    repository = _package_repository()
    repository.package_documents = [
        _document(
            status=DocumentStatusEnum.deleted,
            internship=repository.internship_by_id,
            document_type=repository.required_document_types[0],
            deleted_at=datetime(2026, 6, 2, 9, 0, 0),
        )
    ]
    service = _service(tmp_path, repository=repository)

    package = await service.get_document_package(
        internship_id=7,
        actor=_admin_user(),
    )

    assert package.exportable is False
    assert package.reasons == ["missing_required_documents"]


@pytest.mark.asyncio
async def test_package_selects_latest_approved_document_by_type(tmp_path):
    repository = _package_repository()
    document_type = repository.required_document_types[0]
    older = _document(
        status=DocumentStatusEnum.approved,
        internship=repository.internship_by_id,
        document_id=55,
        document_type=document_type,
        upload_date=datetime(2026, 6, 1, 9, 0, 0),
    )
    newer = _document(
        status=DocumentStatusEnum.approved,
        internship=repository.internship_by_id,
        document_id=56,
        document_type=document_type,
        upload_date=datetime(2026, 6, 2, 9, 0, 0),
    )
    repository.package_documents = [older, newer]
    service = _service(tmp_path, repository=repository)

    package = await service.get_document_package(
        internship_id=7,
        actor=_admin_user(),
    )

    assert package.exportable is True
    assert package.required_documents[0].document.id == 56


@pytest.mark.asyncio
async def test_package_tiebreaks_latest_approved_document_by_id(tmp_path):
    repository = _package_repository()
    document_type = repository.required_document_types[0]
    upload_date = datetime(2026, 6, 1, 9, 0, 0)
    lower_id = _document(
        status=DocumentStatusEnum.approved,
        internship=repository.internship_by_id,
        document_id=55,
        document_type=document_type,
        upload_date=upload_date,
    )
    higher_id = _document(
        status=DocumentStatusEnum.approved,
        internship=repository.internship_by_id,
        document_id=56,
        document_type=document_type,
        upload_date=upload_date,
    )
    repository.package_documents = [lower_id, higher_id]
    service = _service(tmp_path, repository=repository)

    package = await service.get_document_package(
        internship_id=7,
        actor=_admin_user(),
    )

    assert package.exportable is True
    assert package.required_documents[0].document.id == 56


@pytest.mark.asyncio
async def test_package_access_allows_owner_and_document_admin(tmp_path):
    repository = _package_repository()
    service = _service(tmp_path, repository=repository)

    owner_package = await service.get_document_package(
        internship_id=7,
        actor=_user(10, "Estudiante"),
    )
    admin_package = await service.get_document_package(
        internship_id=7,
        actor=_admin_user(),
    )

    assert owner_package.exportable is True
    assert admin_package.exportable is True


@pytest.mark.asyncio
async def test_package_access_rejects_cross_student(tmp_path):
    repository = _package_repository()
    service = _service(tmp_path, repository=repository)

    with pytest.raises(HTTPException) as exc:
        await service.get_document_package(
            internship_id=7,
            actor=_user(99, "Estudiante"),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_package_access_rejects_fica_role(tmp_path):
    repository = _package_repository()
    service = _service(tmp_path, repository=repository)

    with pytest.raises(HTTPException) as exc:
        await service.get_document_package(
            internship_id=7,
            actor=_user(99, "FICA"),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_export_dirae_csv_authorized(tmp_path):
    repository = _package_repository()
    repository.internship_by_id.student.admission_year = 2023
    service = _service(tmp_path, repository=repository)

    export = await service.export_dirae_document_packages(
        actor=_admin_user(),
        internship_ids=[7],
    )
    rows = list(DictReader(StringIO(export.content)))

    assert export.filename.startswith("dirae_document_packages_")
    assert export.filename.endswith(".csv")
    assert rows[0]["internship_id"] == "7"
    assert rows[0]["student_rut"] == "12.345.678-9"
    assert rows[0]["student_enrollment"] == "12345678923"
    assert rows[0]["approved_document_ids"] == "55"
    assert rows[0]["required_document_type_ids"] == "1"
    assert export.audit_event.name == "dirae_export_generated"
    assert export.audit_event.actor_id == 99
    assert export.audit_event.internship_ids == [7]
    assert export.audit_event.approved_document_ids == [55]
    assert export.audit_event.result == "generated"
    assert repository.internship_by_id.dirae_status == DiraeStatusEnum.exported
    assert repository.exported_internships == [repository.internship_by_id]
    assert repository.export_actor_id == 99
    assert repository.export_reason == "dirae_document_package_exported"


@pytest.mark.asyncio
async def test_export_dirae_csv_rejects_non_document_admin(tmp_path):
    repository = _package_repository()
    service = _service(tmp_path, repository=repository)

    with pytest.raises(HTTPException) as exc:
        await service.export_dirae_document_packages(
            actor=_user(10, "Estudiante"),
            internship_ids=[7],
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_export_dirae_csv_returns_404_for_unknown_requested_id(tmp_path):
    repository = _package_repository()
    service = _service(tmp_path, repository=repository)

    with pytest.raises(HTTPException) as exc:
        await service.export_dirae_document_packages(
            actor=_admin_user(),
            internship_ids=[404],
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_export_dirae_csv_returns_409_for_requested_non_exportable(tmp_path):
    repository = _package_repository(status_title="Pendiente")
    service = _service(tmp_path, repository=repository)

    with pytest.raises(HTTPException) as exc:
        await service.export_dirae_document_packages(
            actor=_admin_user(),
            internship_ids=[7],
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["internships"] == [
        {
            "internship_id": 7,
            "reasons": ["internship_not_approved"],
        },
    ]


@pytest.mark.asyncio
async def test_export_dirae_csv_rejects_sensitive_document_for_secretary(tmp_path):
    repository = _package_repository()
    sensitive_type = _document_type(
        2,
        is_required=False,
        name="Seguro escolar",
        is_sensitive=True,
    )
    repository.package_documents.append(
        _document(
            status=DocumentStatusEnum.approved,
            internship=repository.internship_by_id,
            document_id=56,
            document_type=sensitive_type,
        )
    )
    service = _service(tmp_path, repository=repository)

    with pytest.raises(HTTPException) as exc:
        await service.export_dirae_document_packages(
            actor=_admin_user(),
            internship_ids=[7],
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["internships"] == [
        {
            "internship_id": 7,
            "reasons": ["sensitive_document_restricted"],
        },
    ]
    assert repository.exported_internships == []


@pytest.mark.asyncio
async def test_export_dirae_csv_without_ids_can_return_header_only(tmp_path):
    repository = _package_repository(status_title="Pendiente")
    service = _service(tmp_path, repository=repository)

    export = await service.export_dirae_document_packages(
        actor=_admin_user(),
    )

    assert export.content.strip().split(",") == [
        "internship_id",
        "student_id",
        "student_rut",
        "student_enrollment",
        "student_first_name",
        "student_last_name",
        "student_email",
        "degree",
        "cod_degree",
        "internship_type",
        "internship_period",
        "organization",
        "city",
        "start_date",
        "end_date",
        "approved_document_ids",
        "required_document_type_ids",
        "exported_at",
    ]
    assert repository.exported_internships == []
