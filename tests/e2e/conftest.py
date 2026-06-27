import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.config import config
from app.main import app
from app.core.database.database import Base, SessionLocal, engine
from app.modules.auth.models.role_model import Role
from app.modules.auth.models.user_model import User
from app.modules.auth.models.user_role_model import UserRole
from app.modules.auth.services.password_service import PasswordService
from app.modules.auth.utils.roles import (
    CAREER_DIRECTOR_ROLE,
    PRACTICE_MANAGER_ROLE,
    SECRETARY_ROLE,
    STUDENT_ROLE,
)
from app.modules.documents.models.document_model import (
    DocumentCategoryEnum,
    DocumentType,
)
from app.modules.internships.models.current_state_model import CurrentState
from app.modules.internships.models.internship_model import Internship
from app.modules.internships.models.student_internship_requirement_model import (
    RegistrationRequirementType,
    StudentRegistrationRequirement,
)


PASSWORD = "Secret123!"


async def _run_with_clean_pool(coro):
    await engine.dispose()
    try:
        return await coro
    finally:
        await engine.dispose()


def _run(coro):
    return asyncio.run(_run_with_clean_pool(coro))


def _require_test_database() -> None:
    if not (config.POSTGRES_HOST and config.POSTGRES_DB and config.POSTGRES_USER):
        pytest.skip("POSTGRES_* env vars not configured for end-to-end tests")

    if "test" not in config.POSTGRES_DB.lower():
        pytest.skip("End-to-end tests require a PostgreSQL database name containing 'test'")


async def _truncate_tables() -> None:
    table_names = [table.name for table in reversed(Base.metadata.sorted_tables)]
    async with SessionLocal() as session:
        await session.execute(
            text(f"TRUNCATE {', '.join(table_names)} RESTART IDENTITY CASCADE")
        )
        await session.commit()


async def _seed_core_data() -> None:
    async with SessionLocal() as session:
        states = [
            CurrentState(title="Pendiente", description="Solicitud pendiente"),
            CurrentState(title="En revisión", description="Solicitud en revisión"),
            CurrentState(title="En revisión DIRAE", description="Expediente en revisión"),
            CurrentState(title="Aprobada", description="Solicitud aprobada"),
            CurrentState(title="Rechazada", description="Solicitud rechazada"),
        ]
        roles = [
            Role(name=STUDENT_ROLE, description="Estudiante"),
            Role(name=PRACTICE_MANAGER_ROLE, description="Encargado de practica"),
            Role(name=CAREER_DIRECTOR_ROLE, description="Director de carrera"),
            Role(name=SECRETARY_ROLE, description="Secretaria de Carrera"),
        ]
        session.add_all([*states, *roles])
        await session.commit()


async def _create_user(
    *,
    email: str,
    rut: str,
    roles: list[str],
    first_name: str = "Usuario",
    last_name: str = "E2E",
) -> int:
    async with SessionLocal() as session:
        user = User(
            email=email,
            password_hash=PasswordService().hash_password(PASSWORD),
            first_name=first_name,
            last_name=last_name,
            rut=rut,
            degree="Ingenieria Civil Informatica",
            cod_degree="ICI",
            admission_year=2024,
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.flush()

        result = await session.execute(select(Role).where(Role.name.in_(roles)))
        role_by_name = {role.name: role for role in result.scalars().all()}
        session.add_all(
            UserRole(user_id=user.id, role_id=role_by_name[role_name].id)
            for role_name in roles
        )
        await session.commit()
        return user.id


async def _mark_induction_completed(user_id: int) -> None:
    async with SessionLocal() as session:
        session.add(
            StudentRegistrationRequirement(
                user_id=user_id,
                requirement=RegistrationRequirementType.INDUCTION,
                is_completed=True,
                completed_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        await session.commit()


async def _create_document_type() -> int:
    async with SessionLocal() as session:
        document_type = DocumentType(
            name="Formulario de inscripción",
            description="Formulario requerido para el expediente",
            is_required=True,
            category=DocumentCategoryEnum.academic,
            is_sensitive=False,
            is_active=True,
        )
        session.add(document_type)
        await session.commit()
        await session.refresh(document_type)
        return document_type.id


async def _get_internship_status_title(internship_id: int) -> str:
    async with SessionLocal() as session:
        result = await session.execute(
            select(CurrentState.title)
            .join(Internship, Internship.status_id == CurrentState.id)
            .where(Internship.id == internship_id)
        )
        return result.scalar_one()


@pytest.fixture(autouse=True)
def e2e_database(tmp_path: Path):
    _require_test_database()
    original_storage_dir = config.DOCUMENT_STORAGE_DIR
    config.DOCUMENT_STORAGE_DIR = str(tmp_path / "documents")
    _run(_truncate_tables())
    _run(_seed_core_data())
    yield
    _run(_truncate_tables())
    config.DOCUMENT_STORAGE_DIR = original_storage_dir


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def create_user() -> Callable[..., int]:
    def factory(
        *,
        email: str,
        rut: str,
        roles: list[str],
        first_name: str = "Usuario",
        last_name: str = "E2E",
    ) -> int:
        return _run(
            _create_user(
                email=email,
                rut=rut,
                roles=roles,
                first_name=first_name,
                last_name=last_name,
            )
        )

    return factory


@pytest.fixture
def mark_induction_completed() -> Callable[[int], None]:
    def marker(user_id: int) -> None:
        _run(_mark_induction_completed(user_id))

    return marker


@pytest.fixture
def create_document_type() -> Callable[[], int]:
    def factory() -> int:
        return _run(_create_document_type())

    return factory


@pytest.fixture
def internship_status_title() -> Callable[[int], str]:
    def getter(internship_id: int) -> str:
        return _run(_get_internship_status_title(internship_id))

    return getter


@pytest.fixture
def auth_headers(client: TestClient):
    def factory(email: str, password: str = PASSWORD) -> dict[str, str]:
        response = client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return factory


@pytest.fixture
def internship_payload() -> Callable[..., dict]:
    def factory(
        *,
        start_date: str = "2026-04-01",
        end_date: str = "2026-06-15",
        internship_period: str = "Semestre",
        internship_type: str = "Práctica de Estudio I",
        org_name: str = "Empresa E2E SpA",
    ) -> dict:
        return {
            "org_name": org_name,
            "sector": "Tecnologia",
            "address": "Av. Siempre Viva 123",
            "city": "Temuco",
            "org_phone": "+56911111111",
            "web": "https://example.com",
            "supervisor_name": "Supervisor Demo",
            "supervisor_profession": "Ingeniero",
            "supervisor_position": "Jefe de proyecto",
            "supervisor_department": "TI",
            "supervisor_email": "supervisor@example.com",
            "supervisor_phone": "+56922222222",
            "start_date": start_date,
            "end_date": end_date,
            "schedule": "09:00-18:00",
            "days": "Lunes a viernes",
            "modality": "Presencial",
            "internship_address": "Av. Siempre Viva 123",
            "act_description": "Desarrollo de software interno",
            "ben_description": "Apoyo al equipo de ingeniería",
            "amount": 0,
            "internship_period": internship_period,
            "internship_type": internship_type,
        }

    return factory
