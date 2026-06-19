"""Servicio de reportes administrativos agregados."""

import csv
from datetime import UTC, date, datetime
from io import StringIO

from fastapi import HTTPException, status

from app.modules.admin.repositories.admin_report_repository import (
    APPROVED_STATUS,
    REJECTED_STATUSES,
    AdminReportRepository,
)
from app.modules.admin.schemas.admin_report_schema import (
    AdminReportCompliance,
    AdminReportCsvExport,
    AdminReportDistributionItem,
    AdminReportDocuments,
    AdminReportEvaluations,
    AdminReportFilters,
    AdminReportOrganizationItem,
    AdminReportRate,
    AdminReportResponse,
    AdminReportScope,
    AdminReportTimeMetric,
    AdminReportTotal,
)
from app.modules.auth.models.user_model import User
from app.modules.auth.utils.roles import (
    CAREER_DIRECTOR_ROLE,
    FICA_ROLE,
    PRACTICE_MANAGER_ROLE,
)

REPORT_ROLES = [FICA_ROLE, PRACTICE_MANAGER_ROLE, CAREER_DIRECTOR_ROLE]


class AdminReportService:
    """Orquesta los reportes agregados y su exportacion."""

    def __init__(self, repository: AdminReportRepository) -> None:
        self.repository = repository

    async def get_dashboard(
        self,
        filters: AdminReportFilters,
        actor: User,
    ) -> AdminReportResponse:
        """Construye el dashboard agregado con alcance efectivo por actor."""

        scoped_filters, scope = self._apply_scope(filters, actor)
        total_internships = await self.repository.count_internships(scoped_filters)
        total_students = await self.repository.count_students(scoped_filters)
        cancelled = await self.repository.count_cancelled(scoped_filters)
        approved = await self.repository.count_by_status_titles(
            scoped_filters,
            (APPROVED_STATUS,),
        )
        rejected = await self.repository.count_by_status_titles(
            scoped_filters,
            REJECTED_STATUSES,
        )
        required_document_types = await self.repository.required_document_type_count()
        complete_docs, observed_docs, missing_docs, exportable_docs = (
            await self.repository.document_summary(
                scoped_filters,
                required_document_types,
            )
        )
        supervisor_submitted, supervisor_pending = (
            await self.repository.supervisor_evaluation_counts(scoped_filters)
        )
        summer_without_insurance = await self.repository.summer_without_school_insurance(
            scoped_filters,
        )
        overdue_active = await self.repository.overdue_active_internships(
            scoped_filters,
            date.today(),
        )

        status_rows = await self.repository.grouped_by_status(scoped_filters)
        career_rows = await self.repository.grouped_by_career(scoped_filters)
        practice_type_rows = await self.repository.grouped_by_practice_type(scoped_filters)
        period_rows = await self.repository.grouped_by_period(scoped_filters)
        city_rows = await self.repository.grouped_by_city(scoped_filters)
        first_decision_time = await self.repository.time_to_status(
            scoped_filters,
            (APPROVED_STATUS, *REJECTED_STATUSES),
        )
        approval_time = await self.repository.time_to_status(
            scoped_filters,
            (APPROVED_STATUS,),
        )
        organization_rows = await self.repository.recurrent_organizations(scoped_filters)

        return AdminReportResponse(
            generated_at=datetime.now(UTC),
            filters=scoped_filters,
            scope=scope,
            totals=[
                AdminReportTotal(
                    label="Prácticas filtradas",
                    value=total_internships,
                    description="Denominador principal para tasas del reporte.",
                ),
                AdminReportTotal(
                    label="Estudiantes con práctica",
                    value=total_students,
                    description="Usuarios únicos asociados a las prácticas filtradas.",
                ),
                AdminReportTotal(
                    label="Tipos documentales requeridos",
                    value=required_document_types,
                    description="Documentos activos marcados como requeridos.",
                ),
            ],
            by_status=self._distribution(status_rows, total_internships),
            by_career=self._distribution(career_rows, total_internships),
            by_practice_type=self._distribution(practice_type_rows, total_internships),
            by_period=self._distribution(period_rows, total_internships),
            by_city=self._distribution(city_rows, total_internships),
            rates=[
                self._rate(
                    "Tasa de aprobación administrativa",
                    approved,
                    total_internships,
                    "Prácticas con estado actual Aprobada / prácticas filtradas.",
                ),
                self._rate(
                    "Tasa de rechazo administrativa",
                    rejected,
                    total_internships,
                    "Prácticas con estado actual Rechazada/Reprobada / prácticas filtradas.",
                ),
                self._rate(
                    "Tasa de cancelación",
                    cancelled,
                    total_internships,
                    "Prácticas anuladas lógicamente / prácticas filtradas.",
                ),
                AdminReportRate(
                    name="Tasa de finalización",
                    numerator=None,
                    denominator=None,
                    percentage=None,
                    definition=(
                        "No calculada: el modelo actual no posee final_result o "
                        "estado de cierre académico independiente."
                    ),
                    data_available=False,
                ),
            ],
            time_metrics=[
                self._time_metric(
                    "Registro a primera decisión",
                    first_decision_time,
                    "Primer cambio histórico hacia Aprobada/Rechazada/Reprobada.",
                ),
                self._time_metric(
                    "Registro a aprobación administrativa",
                    approval_time,
                    "Primer cambio histórico hacia Aprobada.",
                ),
                AdminReportTimeMetric(
                    name="Registro a finalización",
                    average_days=None,
                    median_days=None,
                    samples=0,
                    definition=(
                        "No calculado: falta entidad activa de cierre/finalización."
                    ),
                    data_available=False,
                ),
            ],
            recurrent_organizations=self._organizations(organization_rows),
            documents=AdminReportDocuments(
                complete_packages=complete_docs,
                observed_packages=observed_docs,
                missing_required_packages=missing_docs,
                exportable_to_dirae=exportable_docs,
                exported_to_dirae=None,
                notes=(
                    "Un paquete completo tiene todos los documentos requeridos "
                    "activos aprobados. Cada exportación DIRAE local persiste "
                    "auditoría de negocio en LogAction."
                ),
            ),
            evaluations=AdminReportEvaluations(
                supervisor_submitted=supervisor_submitted,
                supervisor_pending=supervisor_pending,
                self_evaluation_pending=None,
                data_available=False,
                notes=(
                    "Evaluación de supervisor usa datos reales. Autoevaluación no "
                    "tiene modelo backend activo en este corte."
                ),
            ),
            compliance=AdminReportCompliance(
                summer_without_school_insurance=summer_without_insurance,
                overdue_active_internships=overdue_active,
                pending_finalizations=None,
                nearing_grade_closure=None,
                data_available=False,
                notes=(
                    "Seguro/excepciones y etapas vencidas usan datos reales. Cierre "
                    "de actas no posee agenda/modelo activo aún."
                ),
            ),
        )

    async def export_csv(
        self,
        filters: AdminReportFilters,
        actor: User,
    ) -> AdminReportCsvExport:
        """Genera CSV agregado con los mismos filtros del dashboard."""

        report = await self.get_dashboard(filters, actor)
        content = self._build_csv(report)
        timestamp = report.generated_at.strftime("%Y%m%d_%H%M%S")

        return AdminReportCsvExport(
            filename=f"admin_reports_{timestamp}.csv",
            content=content,
        )

    def _apply_scope(
        self,
        filters: AdminReportFilters,
        actor: User,
    ) -> tuple[AdminReportFilters, AdminReportScope]:
        role_names = [user_role.role.name for user_role in actor.roles if user_role.role]
        primary_role = next((role for role in REPORT_ROLES if role in role_names), role_names[0])

        if primary_role == FICA_ROLE:
            return filters, AdminReportScope(role=primary_role, is_cross_career=True)

        actor_career_code = getattr(actor, "cod_degree", None)
        if actor_career_code:
            if filters.career_code and filters.career_code != actor_career_code:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot request reports outside actor career scope",
                )
            filters = filters.model_copy(update={"career_code": actor_career_code})

        return filters, AdminReportScope(
            role=primary_role,
            is_cross_career=False,
            career_code=actor_career_code,
        )

    def _distribution(
        self,
        rows: list[tuple[str, int]],
        denominator: int,
    ) -> list[AdminReportDistributionItem]:
        return [
            AdminReportDistributionItem(
                name=name,
                total=total,
                percentage=self._percentage(total, denominator),
            )
            for name, total in rows
        ]

    def _rate(
        self,
        name: str,
        numerator: int,
        denominator: int,
        definition: str,
    ) -> AdminReportRate:
        return AdminReportRate(
            name=name,
            numerator=numerator,
            denominator=denominator,
            percentage=self._percentage(numerator, denominator),
            definition=definition,
        )

    def _time_metric(
        self,
        name: str,
        values: tuple[float | None, float | None, int],
        definition: str,
    ) -> AdminReportTimeMetric:
        average_days, median_days, samples = values

        return AdminReportTimeMetric(
            name=name,
            average_days=self._round_or_none(average_days),
            median_days=self._round_or_none(median_days),
            samples=samples,
            definition=definition,
            data_available=samples > 0,
        )

    def _organizations(
        self,
        rows: list[tuple[str, str, int, int, int, int]],
    ) -> list[AdminReportOrganizationItem]:
        return [
            AdminReportOrganizationItem(
                normalized_name=normalized_name,
                display_name=display_name,
                total=total,
                approved=approved or 0,
                rejected=rejected or 0,
                cancelled=cancelled or 0,
            )
            for normalized_name, display_name, total, approved, rejected, cancelled in rows
        ]

    def _build_csv(self, report: AdminReportResponse) -> str:
        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["section", "metric", "value", "denominator", "percentage", "notes"],
        )
        writer.writeheader()

        for total in report.totals:
            writer.writerow(
                {
                    "section": "totals",
                    "metric": total.label,
                    "value": total.value,
                    "denominator": total.denominator or "",
                    "percentage": "",
                    "notes": total.description,
                }
            )
        for rate in report.rates:
            writer.writerow(
                {
                    "section": "rates",
                    "metric": rate.name,
                    "value": "" if rate.numerator is None else rate.numerator,
                    "denominator": "" if rate.denominator is None else rate.denominator,
                    "percentage": "" if rate.percentage is None else rate.percentage,
                    "notes": rate.definition,
                }
            )
        for section, rows in (
            ("by_status", report.by_status),
            ("by_career", report.by_career),
            ("by_practice_type", report.by_practice_type),
            ("by_period", report.by_period),
            ("by_city", report.by_city),
        ):
            for row in rows:
                writer.writerow(
                    {
                        "section": section,
                        "metric": row.name,
                        "value": row.total,
                        "denominator": report.totals[0].value,
                        "percentage": row.percentage,
                        "notes": "Agregado sin datos personales.",
                    }
                )
        for org in report.recurrent_organizations:
            writer.writerow(
                {
                    "section": "organizations",
                    "metric": org.display_name,
                    "value": org.total,
                    "denominator": report.totals[0].value,
                    "percentage": "",
                    "notes": (
                        f"approved={org.approved}; rejected={org.rejected}; "
                        f"cancelled={org.cancelled}"
                    ),
                }
            )

        writer.writerow(
            {
                "section": "documents",
                "metric": "complete_packages",
                "value": report.documents.complete_packages,
                "denominator": report.totals[0].value,
                "percentage": "",
                "notes": report.documents.notes,
            }
        )

        return output.getvalue()

    def _percentage(self, numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0

        return round((numerator / denominator) * 100, 2)

    def _round_or_none(self, value: float | None) -> float | None:
        if value is None:
            return None

        return round(float(value), 2)
