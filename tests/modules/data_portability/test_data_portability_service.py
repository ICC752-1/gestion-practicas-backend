from datetime import date, datetime
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from fastapi import HTTPException

from app.modules.data_portability.models.data_portability_model import (
    DataPortabilityStatusEnum,
)
from app.modules.data_portability.repositories.data_portability_repository import (
    DataPortabilityRepository,
)
from app.modules.data_portability.services.data_portability_service import (
    DataPortabilityService,
)


class FakeDataPortabilityRepository:
    def __init__(self, tmp_path: Path) -> None:
        self.user = _user()
        self.internships = [_internship()]
        self.history = []
        self.exceptions = []
        self.documents = [_document()]
        self.presentation_letters = [_presentation_letter()]
        self.self_evaluations = []
        self.supervisor_evaluations = []
        self.requests = []
        self.tmp_path = tmp_path

    async def get_user(self, user_id: int):
        return self.user if self.user.id == user_id else None

    async def list_internships(self, user_id: int):
        return self.internships

    async def list_status_history(self, internship_ids: list[int]):
        return self.history

    async def list_exceptions(self, internship_ids: list[int]):
        return self.exceptions

    async def list_documents(self, user_id: int, internship_ids: list[int]):
        return self.documents

    async def list_presentation_letters(self, user_id: int):
        return self.presentation_letters

    async def list_self_evaluations(self, user_id: int):
        return self.self_evaluations

    async def list_supervisor_evaluations(self, internship_ids: list[int]):
        return self.supervisor_evaluations

    async def create_request(self, request):
        request.id = 1
        request.requested_at = datetime(2026, 6, 18, 10, 0, 0)
        self.requests.append(request)
        return request

    async def save_request(self, request):
        self.requests[-1] = request
        return request


class FakeQueryResult:
    def scalars(self):
        return self

    def all(self):
        return []


class FakeDb:
    def __init__(self) -> None:
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return FakeQueryResult()


def _role(name: str) -> SimpleNamespace:
    return SimpleNamespace(role=SimpleNamespace(name=name))


def _user() -> SimpleNamespace:
    return SimpleNamespace(
        id=10,
        email="juan.perez@correo.cl",
        first_name="Juan",
        last_name="Perez",
        rut="11.111.111-1",
        enrollment="11111111126",
        admission_year=2026,
        degree="Ingenieria Civil Informatica",
        cod_degree="INF-001",
        sexo="Masculino",
        phone="+56912345678",
        is_active=True,
        is_verified=True,
        created_at=datetime(2026, 1, 1, 9, 0, 0),
        roles=[_role("Estudiante")],
    )


def _internship() -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        org_name="Empresa Demo",
        sector="Tecnologia",
        address="Av. Alemania 123",
        city="Temuco",
        org_phone="+56451234567",
        web="https://empresa.example",
        supervisor_name="Ana Perez",
        supervisor_profession="Ingeniera",
        supervisor_position="Jefa",
        supervisor_department="TI",
        supervisor_email="ana@example.com",
        supervisor_phone="+56911111111",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 6, 1),
        schedule="09:00-18:00",
        days="Lunes a viernes",
        modality="Presencial",
        internship_address="Av. Alemania 123",
        act_description="Desarrollo de software",
        ben_description="Asignación de colación",
        amount=120000,
        internship_period=SimpleNamespace(value="Semestre"),
        internship_type=SimpleNamespace(value="Práctica de Estudio I"),
        status=SimpleNamespace(title="Aprobada"),
        completion_status=SimpleNamespace(value="finalized"),
        final_result=SimpleNamespace(value="passed"),
        has_school_insurance=True,
        insurance_status=SimpleNamespace(value="valid"),
        insurance_validated_at=datetime(2026, 2, 1, 12, 0, 0),
        insurance_notes=None,
        is_cancelled=False,
        cancelled_at=None,
        cancellation_reason=None,
        upload_date=datetime(2026, 2, 1, 10, 0, 0),
    )


def _document() -> SimpleNamespace:
    return SimpleNamespace(
        id=33,
        internship_id=7,
        user_id=99,
        document_type=SimpleNamespace(name="Formulario"),
        file_name="formulario.pdf",
        file_path="7/formulario.pdf",
        extension=SimpleNamespace(value="pdf"),
        status=SimpleNamespace(value="approved"),
        size_bytes=5,
        upload_date=datetime(2026, 2, 2, 10, 0, 0),
        reviewed_at=None,
        review_comment=None,
    )


def _presentation_letter() -> SimpleNamespace:
    return SimpleNamespace(
        id=44,
        student_id=10,
        practice_type="Práctica de Estudio I",
        generated_file_name="carta-presentacion.pdf",
        generated_file_path="10/practica-i/carta-presentacion.pdf",
        recipient_email="juan.perez@correo.cl",
        sent_at=datetime(2026, 2, 3, 10, 0, 0),
        downloaded_at=None,
        created_at=datetime(2026, 2, 3, 9, 55, 0),
    )


async def test_export_json_minimizes_sensitive_user_fields(tmp_path: Path) -> None:
    repository = FakeDataPortabilityRepository(tmp_path)
    service = DataPortabilityService(
        repository,
        app_config=SimpleNamespace(DOCUMENT_STORAGE_DIR=str(tmp_path)),
    )

    export = await service.export_my_data(
        actor=repository.user,
        export_format="json",
        include_documents=False,
    )

    content = export.content.decode("utf-8")
    assert export.media_type == "application/json"
    assert "password_hash" not in content
    assert "token" not in content
    assert "storage/documents" not in content
    assert "juan.perez@correo.cl" in content
    assert repository.requests[-1].status == DataPortabilityStatusEnum.completed


async def test_export_pdf_generates_readable_report(tmp_path: Path) -> None:
    repository = FakeDataPortabilityRepository(tmp_path)
    service = DataPortabilityService(
        repository,
        app_config=SimpleNamespace(
            DOCUMENT_STORAGE_DIR=str(tmp_path / "documents"),
            PRESENTATION_LETTER_STORAGE_DIR=str(tmp_path / "letters"),
        ),
    )

    export = await service.export_my_data(
        actor=repository.user,
        export_format="pdf",
        include_documents=False,
    )

    assert export.media_type == "application/pdf"
    assert export.filename.endswith(".pdf")
    assert export.content.startswith(b"%PDF")


async def test_export_zip_includes_report_manifest_and_related_files(
    tmp_path: Path,
) -> None:
    repository = FakeDataPortabilityRepository(tmp_path)
    document_root = tmp_path / "documents"
    letter_root = tmp_path / "letters"
    document_path = document_root / repository.documents[0].file_path
    letter_path = (
        letter_root / repository.presentation_letters[0].generated_file_path
    )
    document_path.parent.mkdir(parents=True)
    letter_path.parent.mkdir(parents=True)
    document_path.write_bytes(b"documento")
    letter_path.write_bytes(b"%PDF-carta")
    service = DataPortabilityService(
        repository,
        app_config=SimpleNamespace(
            DOCUMENT_STORAGE_DIR=str(document_root),
            PRESENTATION_LETTER_STORAGE_DIR=str(letter_root),
        ),
    )

    export = await service.export_my_data(
        actor=repository.user,
        export_format="zip",
        include_documents=True,
    )

    with ZipFile(BytesIO(export.content)) as archive:
        names = set(archive.namelist())
        assert "resumen_estudiante.pdf" in names
        assert "datos/data.json" in names
        assert "manifest.json" in names
        assert "LEEME.txt" in names
        assert "documentos/practica_7/33_formulario.pdf" in names
        assert (
            "documentos_generados/cartas_presentacion/"
            "44_carta-presentacion.pdf"
        ) in names

        payload = json.loads(archive.read("datos/data.json"))
        manifest = json.loads(archive.read("manifest.json"))

    assert payload["documents"][0]["source"] == "related_actor"
    assert payload["presentation_letters"][0]["included_in_zip"] is True
    assert all(item["sha256"] for item in manifest["files"])
    assert manifest["missing_files"] == []


async def test_export_requires_student_role(tmp_path: Path) -> None:
    repository = FakeDataPortabilityRepository(tmp_path)
    repository.user.roles = [_role("Director de carrera")]
    service = DataPortabilityService(repository)

    with pytest.raises(HTTPException) as error:
        await service.export_my_data(
            actor=repository.user,
            export_format="json",
            include_documents=False,
        )

    assert error.value.status_code == 403


async def test_document_query_includes_files_related_to_student_internships() -> None:
    db = FakeDb()
    repository = DataPortabilityRepository(db)

    await repository.list_documents(user_id=10, internship_ids=[7, 8])

    compiled = str(db.statement.compile(compile_kwargs={"literal_binds": True}))
    assert "document.user_id = 10" in compiled
    assert "document.internship_id IN (7, 8)" in compiled
    assert " OR " in compiled
