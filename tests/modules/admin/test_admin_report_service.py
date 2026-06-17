from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.main import app
from app.modules.admin.schemas.admin_report_schema import AdminReportFilters
from app.modules.admin.services.admin_report_service import (
    REPORT_ROLES,
    AdminReportService,
)
from app.modules.auth.dependencies.role_dependency import require_roles


def _methods_for_path(path: str) -> set[str]:
    methods: set[str] = set()

    for route in app.routes:
        if route.path == path and hasattr(route, "methods"):
            methods.update(route.methods)

    return methods


def _user(*roles: str, cod_degree: str | None = None):
    return SimpleNamespace(
        id=1,
        cod_degree=cod_degree,
        roles=[SimpleNamespace(role=SimpleNamespace(name=role)) for role in roles],
    )


class FakeReportRepository:
    def __init__(self) -> None:
        self.last_filters = None

    def _remember(self, filters: AdminReportFilters) -> None:
        self.last_filters = filters

    async def count_internships(self, filters: AdminReportFilters) -> int:
        self._remember(filters)
        return 4

    async def count_students(self, filters: AdminReportFilters) -> int:
        self._remember(filters)
        return 3

    async def count_cancelled(self, filters: AdminReportFilters) -> int:
        self._remember(filters)
        return 1

    async def count_by_status_titles(
        self,
        filters: AdminReportFilters,
        status_titles: tuple[str, ...],
    ) -> int:
        self._remember(filters)
        if "Aprobada" in status_titles:
            return 2
        return 1

    async def required_document_type_count(self) -> int:
        return 2

    async def document_summary(
        self,
        filters: AdminReportFilters,
        required_type_count: int,
    ) -> tuple[int, int, int, int]:
        self._remember(filters)
        assert required_type_count == 2
        return 2, 1, 2, 2

    async def supervisor_evaluation_counts(
        self,
        filters: AdminReportFilters,
    ) -> tuple[int, int]:
        self._remember(filters)
        return 1, 3

    async def summer_without_school_insurance(self, filters: AdminReportFilters) -> int:
        self._remember(filters)
        return 1

    async def overdue_active_internships(self, filters: AdminReportFilters, today) -> int:
        self._remember(filters)
        return 2

    async def grouped_by_status(self, filters: AdminReportFilters):
        self._remember(filters)
        return [("Aprobada", 2), ("Rechazada", 1), ("Pendiente", 1)]

    async def grouped_by_career(self, filters: AdminReportFilters):
        self._remember(filters)
        return [("Ingeniería Civil Informática", 4)]

    async def grouped_by_practice_type(self, filters: AdminReportFilters):
        self._remember(filters)
        return [("Práctica de Estudio I", 4)]

    async def grouped_by_period(self, filters: AdminReportFilters):
        self._remember(filters)
        return [("Verano", 4)]

    async def grouped_by_city(self, filters: AdminReportFilters):
        self._remember(filters)
        return [("Temuco", 4)]

    async def time_to_status(
        self,
        filters: AdminReportFilters,
        status_titles: tuple[str, ...],
    ):
        self._remember(filters)
        if status_titles == ("Aprobada",):
            return 7.125, 6.0, 2
        return 5.0, 4.5, 3

    async def recurrent_organizations(self, filters: AdminReportFilters):
        self._remember(filters)
        return [("acme spa", "ACME SpA", 2, 1, 1, 0)]


def test_admin_report_routes_are_registered() -> None:
    assert "GET" in _methods_for_path("/admin/reports/dashboard")
    assert "GET" in _methods_for_path("/admin/reports/export.csv")


@pytest.mark.parametrize(
    "role",
    ["FICA", "Encargado de practica", "Director de carrera"],
)
async def test_admin_report_roles_are_authorized(role: str) -> None:
    dependency = require_roles(REPORT_ROLES)

    result = await dependency(_user(role))

    assert result.roles[0].role.name == role


@pytest.mark.parametrize(
    "role",
    ["Secretaria de Carrera", "Estudiante", "Supervisor de practica", "Superadmin"],
)
async def test_admin_report_rejects_non_report_roles(role: str) -> None:
    dependency = require_roles(REPORT_ROLES)

    with pytest.raises(HTTPException) as exc_info:
        await dependency(_user(role))

    assert exc_info.value.status_code == 403


async def test_fica_report_uses_cross_career_scope() -> None:
    repository = FakeReportRepository()
    service = AdminReportService(repository)

    report = await service.get_dashboard(AdminReportFilters(), _user("FICA"))

    assert report.scope.is_cross_career is True
    assert report.scope.career_code is None
    assert report.totals[0].value == 4
    assert report.rates[0].percentage == 50.0
    assert report.recurrent_organizations[0].display_name == "ACME SpA"


async def test_director_scope_forces_own_career_code() -> None:
    repository = FakeReportRepository()
    service = AdminReportService(repository)

    report = await service.get_dashboard(
        AdminReportFilters(),
        _user("Director de carrera", cod_degree="ICI"),
    )

    assert report.scope.is_cross_career is False
    assert repository.last_filters.career_code == "ICI"


async def test_director_cannot_request_other_career_code() -> None:
    repository = FakeReportRepository()
    service = AdminReportService(repository)

    with pytest.raises(HTTPException) as exc_info:
        await service.get_dashboard(
            AdminReportFilters(career_code="ICO"),
            _user("Director de carrera", cod_degree="ICI"),
        )

    assert exc_info.value.status_code == 403


async def test_report_csv_is_aggregate_without_personal_fields() -> None:
    service = AdminReportService(FakeReportRepository())

    export = await service.export_csv(AdminReportFilters(), _user("FICA"))

    assert "rut" not in export.content.lower()
    assert "email" not in export.content.lower()
    assert "ACME SpA" in export.content
    assert "Prácticas filtradas" in export.content
