"""Schemas HTTP para reportes administrativos agregados."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class AdminReportFilters(BaseModel):
    """Filtros comunes disponibles para los reportes agregados."""

    date_from: date | None = None
    date_to: date | None = None
    career: str | None = None
    career_code: str | None = None
    practice_type: str | None = None
    period: str | None = None
    status: str | None = None
    organization: str | None = None
    city: str | None = None
    timezone: str = "America/Santiago"


class AdminReportScope(BaseModel):
    """Alcance aplicado segun rol del actor."""

    role: str
    is_cross_career: bool
    career_code: str | None = None


class AdminReportTotal(BaseModel):
    """Total principal con denominador explicito."""

    label: str
    value: int
    denominator: int | None = None
    description: str
    data_available: bool = True


class AdminReportDistributionItem(BaseModel):
    """Fila de distribucion agregada."""

    name: str
    total: int
    percentage: float


class AdminReportRate(BaseModel):
    """Indicador calculado con numerador y denominador."""

    name: str
    numerator: int | None
    denominator: int | None
    percentage: float | None
    definition: str
    data_available: bool = True


class AdminReportTimeMetric(BaseModel):
    """Indicador de tiempo calculado desde historial de estados."""

    name: str
    average_days: float | None
    median_days: float | None
    samples: int
    definition: str
    data_available: bool = True


class AdminReportOrganizationItem(BaseModel):
    """Organizacion recurrente normalizada."""

    normalized_name: str
    display_name: str
    total: int
    approved: int
    rejected: int
    cancelled: int


class AdminReportDocuments(BaseModel):
    """Resumen documental agregado."""

    complete_packages: int
    observed_packages: int
    missing_required_packages: int
    exportable_to_dirae: int
    exported_to_dirae: int | None
    data_available: bool = True
    notes: str


class AdminReportEvaluations(BaseModel):
    """Resumen agregado de evaluaciones disponibles."""

    supervisor_submitted: int
    supervisor_pending: int
    self_evaluation_pending: int | None
    data_available: bool
    notes: str


class AdminReportCompliance(BaseModel):
    """Indicadores de cumplimiento y alertas."""

    summer_without_school_insurance: int
    overdue_active_internships: int
    pending_finalizations: int | None
    nearing_grade_closure: int | None
    data_available: bool
    notes: str


class AdminReportResponse(BaseModel):
    """Respuesta principal de dashboard agregado."""

    model_config = ConfigDict(from_attributes=True)

    generated_at: datetime
    filters: AdminReportFilters
    scope: AdminReportScope
    totals: list[AdminReportTotal]
    by_status: list[AdminReportDistributionItem]
    by_career: list[AdminReportDistributionItem]
    by_practice_type: list[AdminReportDistributionItem]
    by_period: list[AdminReportDistributionItem]
    by_city: list[AdminReportDistributionItem]
    rates: list[AdminReportRate]
    time_metrics: list[AdminReportTimeMetric]
    recurrent_organizations: list[AdminReportOrganizationItem]
    documents: AdminReportDocuments
    evaluations: AdminReportEvaluations
    compliance: AdminReportCompliance


class AdminReportCsvExport(BaseModel):
    """CSV generado para descarga."""

    filename: str
    content: str = Field(description="Contenido CSV UTF-8 sin datos personales.")


class AdminReportPdfExport(BaseModel):
    """PDF ejecutivo generado para descarga."""

    filename: str
    content: bytes = Field(description="Contenido PDF sin datos personales.")
