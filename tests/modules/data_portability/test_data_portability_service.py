from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.modules.data_portability.models.data_portability_model import (
    DataPortabilityStatusEnum,
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

    async def list_documents(self, user_id: int):
        return self.documents

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


def _role(name: str) -> SimpleNamespace:
    return SimpleNamespace(role=SimpleNamespace(name=name))


def _user() -> SimpleNamespace:
    return SimpleNamespace(
        id=10,
        email="juan.perez@correo.cl",
        first_name="Juan",
        last_name="Perez",
        rut="11.111.111-1",
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
        city="Temuco",
        supervisor_name="Ana Perez",
        supervisor_profession="Ingeniera",
        supervisor_position="Jefa",
        supervisor_department="TI",
        supervisor_email="ana@example.com",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 6, 1),
        schedule="09:00-18:00",
        days="Lunes a viernes",
        modality="Presencial",
        internship_period=SimpleNamespace(value="Semestre"),
        internship_type=SimpleNamespace(value="Práctica de Estudio I"),
        status=SimpleNamespace(title="Aprobada"),
        completion_status=SimpleNamespace(value="finalized"),
        final_result=SimpleNamespace(value="passed"),
        is_cancelled=False,
        cancellation_reason=None,
        upload_date=datetime(2026, 2, 1, 10, 0, 0),
    )


def _document() -> SimpleNamespace:
    return SimpleNamespace(
        id=33,
        internship_id=7,
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
