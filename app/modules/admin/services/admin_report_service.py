"""Servicio de reportes administrativos agregados."""

import csv
from datetime import UTC, date, datetime
from html import escape
from io import BytesIO, StringIO

from fastapi import HTTPException, status
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

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
    AdminReportPdfExport,
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
        self_submitted, self_pending = await self._self_evaluation_counts(
            scoped_filters,
            total_internships,
        )
        finalized = await self._finalized_internship_count(scoped_filters)
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
                    numerator=finalized,
                    denominator=total_internships,
                    percentage=round((finalized / total_internships) * 100, 2)
                    if total_internships
                    else 0.0,
                    definition=(
                        "Prácticas con completion_status=finalized / prácticas filtradas."
                    ),
                    data_available=True,
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
                self_evaluation_pending=self_pending,
                data_available=True,
                notes=(
                    "Evaluación de supervisor y autoevaluación usan datos reales. "
                    f"Autoevaluaciones enviadas: {self_submitted}."
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

    async def export_pdf(
        self,
        filters: AdminReportFilters,
        actor: User,
    ) -> AdminReportPdfExport:
        """Genera un informe ejecutivo PDF con los datos agregados del dashboard."""

        report = await self.get_dashboard(filters, actor)
        content = self._build_pdf(report)
        timestamp = report.generated_at.strftime("%Y%m%d_%H%M%S")

        return AdminReportPdfExport(
            filename=f"reporte_institucional_fica_{timestamp}.pdf",
            content=content,
        )

    async def _self_evaluation_counts(
        self,
        filters: AdminReportFilters,
        total_internships: int,
    ) -> tuple[int, int]:
        if not hasattr(self.repository, "self_evaluation_counts"):
            return 0, total_internships
        return await self.repository.self_evaluation_counts(filters)

    async def _finalized_internship_count(self, filters: AdminReportFilters) -> int:
        if not hasattr(self.repository, "finalized_internship_count"):
            return 0
        return await self.repository.finalized_internship_count(filters)

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

    def _build_pdf(self, report: AdminReportResponse) -> bytes:
        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=16 * mm,
            leftMargin=16 * mm,
            topMargin=14 * mm,
            bottomMargin=14 * mm,
            title="Reporte institucional de prácticas FICA",
            author="Sistema de Gestión de Prácticas",
        )
        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="ReportTitle",
                parent=styles["Title"],
                alignment=TA_CENTER,
                fontName="Helvetica-Bold",
                fontSize=18,
                leading=22,
                textColor=colors.HexColor("#111827"),
                spaceAfter=6,
            )
        )
        styles.add(
            ParagraphStyle(
                name="ReportSubtitle",
                parent=styles["Normal"],
                alignment=TA_CENTER,
                fontSize=9,
                leading=12,
                textColor=colors.HexColor("#4B5563"),
                spaceAfter=14,
            )
        )
        styles.add(
            ParagraphStyle(
                name="ReportSection",
                parent=styles["Heading2"],
                fontName="Helvetica-Bold",
                fontSize=12,
                leading=15,
                textColor=colors.HexColor("#8B1D46"),
                spaceBefore=10,
                spaceAfter=6,
            )
        )
        styles.add(
            ParagraphStyle(
                name="ReportCell",
                parent=styles["Normal"],
                fontSize=8,
                leading=10,
                textColor=colors.HexColor("#111827"),
            )
        )
        styles.add(
            ParagraphStyle(
                name="ReportMuted",
                parent=styles["Normal"],
                fontSize=8,
                leading=10,
                textColor=colors.HexColor("#6B7280"),
            )
        )

        scope = (
            "Todas las carreras"
            if report.scope.is_cross_career
            else f"Carrera {report.scope.career_code or 'no informada'}"
        )
        story: list[object] = [
            Paragraph("Reporte institucional de prácticas FICA", styles["ReportTitle"]),
            Paragraph(
                (
                    f"Generado el {self._pdf_datetime(report.generated_at)} · "
                    f"Alcance: {escape(scope)}"
                ),
                styles["ReportSubtitle"],
            ),
            Paragraph("Resumen ejecutivo", styles["ReportSection"]),
        ]

        approval_rate = self._find_rate(report, "Tasa de aprobación administrativa")
        completion_rate = self._find_rate(report, "Tasa de finalización")
        summary_rows = [
            [self._cell("Indicador", styles, bold=True), self._cell("Resultado", styles, bold=True)],
            *[
                [self._cell(item.label, styles), self._cell(str(item.value), styles)]
                for item in report.totals[:2]
            ],
            [
                self._cell("Tasa de aprobación", styles),
                self._cell(self._pdf_percentage(approval_rate), styles),
            ],
            [
                self._cell("Tasa de finalización", styles),
                self._cell(self._pdf_percentage(completion_rate), styles),
            ],
        ]
        story.append(self._pdf_table(summary_rows, [115 * mm, 45 * mm]))

        story.extend(
            [
                Paragraph("Alertas prioritarias", styles["ReportSection"]),
                self._pdf_table(
                    [
                        [
                            self._cell("Alerta", styles, bold=True),
                            self._cell("Casos", styles, bold=True),
                            self._cell("Acción sugerida", styles, bold=True),
                        ],
                        [
                            self._cell("Prácticas de verano sin seguro o excepción", styles),
                            self._cell(
                                str(report.compliance.summer_without_school_insurance),
                                styles,
                            ),
                            self._cell("Revisar con Secretaría o Dirección", styles),
                        ],
                        [
                            self._cell("Prácticas activas con etapas vencidas", styles),
                            self._cell(
                                str(report.compliance.overdue_active_internships),
                                styles,
                            ),
                            self._cell("Solicitar actualización del seguimiento", styles),
                        ],
                        [
                            self._cell("Evaluaciones de supervisor pendientes", styles),
                            self._cell(str(report.evaluations.supervisor_pending), styles),
                            self._cell("Gestionar envío con supervisores", styles),
                        ],
                    ],
                    [80 * mm, 20 * mm, 60 * mm],
                ),
                Paragraph("Documentación y DIRAE", styles["ReportSection"]),
            ]
        )
        required_document_types = next(
            (
                total.value
                for total in report.totals
                if total.label == "Tipos documentales requeridos"
            ),
            0,
        )
        if required_document_types == 0:
            story.append(
                Paragraph(
                    (
                        "No hay requisitos documentales configurados. Los tipos "
                        "documentales activos están definidos como opcionales."
                    ),
                    styles["ReportMuted"],
                )
            )
        else:
            story.append(
                self._pdf_table(
                    [
                        [
                            self._cell("Paquetes completos", styles, bold=True),
                            self._cell("Observados", styles, bold=True),
                            self._cell("Con faltantes", styles, bold=True),
                            self._cell("Listos para DIRAE", styles, bold=True),
                        ],
                        [
                            self._cell(str(report.documents.complete_packages), styles),
                            self._cell(str(report.documents.observed_packages), styles),
                            self._cell(
                                str(report.documents.missing_required_packages),
                                styles,
                            ),
                            self._cell(str(report.documents.exportable_to_dirae), styles),
                        ],
                    ],
                    [40 * mm] * 4,
                )
            )

        distributions = (
            ("Estado", report.by_status),
            ("Carrera", report.by_career),
            ("Tipo de práctica", report.by_practice_type),
            ("Periodo académico", report.by_period),
            ("Ciudad", report.by_city),
        )
        for title, rows in distributions:
            story.append(Paragraph(f"Distribución por {title.lower()}", styles["ReportSection"]))
            if not rows:
                story.append(
                    Paragraph(
                        "Sin datos para los filtros aplicados.",
                        styles["ReportMuted"],
                    )
                )
                continue
            story.append(
                self._pdf_table(
                    [
                        [
                            self._cell(title, styles, bold=True),
                            self._cell("Total", styles, bold=True),
                            self._cell("Porcentaje", styles, bold=True),
                        ],
                        *[
                            [
                                self._cell(row.name, styles),
                                self._cell(str(row.total), styles),
                                self._cell(f"{row.percentage:.2f}%", styles),
                            ]
                            for row in rows
                        ],
                    ],
                    [105 * mm, 25 * mm, 30 * mm],
                )
            )

        story.extend(
            [
                PageBreak(),
                Paragraph("Tiempos de tramitación", styles["ReportSection"]),
            ]
        )
        story.append(
            self._pdf_table(
                [
                    [
                        self._cell("Indicador", styles, bold=True),
                        self._cell("Promedio", styles, bold=True),
                        self._cell("Mediana", styles, bold=True),
                        self._cell("Muestras", styles, bold=True),
                    ],
                    *[
                        [
                            self._cell(metric.name, styles),
                            self._cell(self._pdf_days(metric.average_days), styles),
                            self._cell(self._pdf_days(metric.median_days), styles),
                            self._cell(str(metric.samples), styles),
                        ]
                        for metric in report.time_metrics
                    ],
                ],
                [85 * mm, 27 * mm, 27 * mm, 21 * mm],
            )
        )

        story.append(Paragraph("Organizaciones recurrentes", styles["ReportSection"]))
        if report.recurrent_organizations:
            story.append(
                self._pdf_table(
                    [
                        [
                            self._cell("Organización", styles, bold=True),
                            self._cell("Total", styles, bold=True),
                            self._cell("Aprobadas", styles, bold=True),
                            self._cell("Rechazadas", styles, bold=True),
                            self._cell("Canceladas", styles, bold=True),
                        ],
                        *[
                            [
                                self._cell(org.display_name, styles),
                                self._cell(str(org.total), styles),
                                self._cell(str(org.approved), styles),
                                self._cell(str(org.rejected), styles),
                                self._cell(str(org.cancelled), styles),
                            ]
                            for org in report.recurrent_organizations
                        ],
                    ],
                    [80 * mm, 20 * mm, 20 * mm, 20 * mm, 20 * mm],
                )
            )
        else:
            story.append(
                Paragraph(
                    "No hay organizaciones recurrentes para los filtros aplicados.",
                    styles["ReportMuted"],
                )
            )

        story.extend(
            [
                Spacer(1, 8),
                Paragraph(
                    (
                        "Este informe contiene información agregada y no incluye RUT, "
                        "correos, matrículas ni documentos individuales."
                    ),
                    styles["ReportMuted"],
                ),
            ]
        )
        document.build(story)
        return buffer.getvalue()

    def _pdf_table(self, rows: list[list[Paragraph]], widths: list[float]) -> Table:
        table = Table(rows, colWidths=widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#374151")),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D1D5DB")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
                ]
            )
        )
        return table

    def _cell(
        self,
        value: str,
        styles,
        *,
        bold: bool = False,
    ) -> Paragraph:
        content = escape(value or "Sin dato")
        if bold:
            content = f"<b>{content}</b>"
        return Paragraph(content, styles["ReportCell"])

    def _find_rate(
        self,
        report: AdminReportResponse,
        name: str,
    ) -> AdminReportRate | None:
        return next((rate for rate in report.rates if rate.name == name), None)

    def _pdf_percentage(self, rate: AdminReportRate | None) -> str:
        if rate is None or rate.percentage is None:
            return "Sin dato"
        return f"{rate.percentage:.2f}%"

    def _pdf_days(self, value: float | None) -> str:
        return "Sin dato" if value is None else f"{value:.2f} días"

    def _pdf_datetime(self, value: datetime) -> str:
        return value.strftime("%d-%m-%Y %H:%M UTC")

    def _percentage(self, numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0

        return round((numerator / denominator) * 100, 2)

    def _round_or_none(self, value: float | None) -> float | None:
        if value is None:
            return None

        return round(float(value), 2)
