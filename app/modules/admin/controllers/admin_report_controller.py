"""Controlador HTTP para reportes administrativos agregados."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.database import get_db
from app.modules.admin.repositories.admin_report_repository import AdminReportRepository
from app.modules.admin.schemas.admin_report_schema import (
    AdminReportFilters,
    AdminReportResponse,
)
from app.modules.admin.services.admin_report_service import (
    REPORT_ROLES,
    AdminReportService,
)
from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.auth.models.user_model import User

router = APIRouter(prefix="/admin/reports", tags=["Admin reports"])


def _build_service(db: AsyncSession) -> AdminReportService:
    return AdminReportService(AdminReportRepository(db))


def _build_filters(
    date_from: date | None,
    date_to: date | None,
    career: str | None,
    career_code: str | None,
    practice_type: str | None,
    period: str | None,
    status: str | None,
    organization: str | None,
    city: str | None,
    timezone: str,
) -> AdminReportFilters:
    return AdminReportFilters(
        date_from=date_from,
        date_to=date_to,
        career=career,
        career_code=career_code,
        practice_type=practice_type,
        period=period,
        status=status,
        organization=organization,
        city=city,
        timezone=timezone,
    )


@router.get("/dashboard", response_model=AdminReportResponse)
async def get_admin_report_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(REPORT_ROLES))],
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    career: Annotated[str | None, Query()] = None,
    career_code: Annotated[str | None, Query()] = None,
    practice_type: Annotated[str | None, Query()] = None,
    period: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    organization: Annotated[str | None, Query()] = None,
    city: Annotated[str | None, Query()] = None,
    timezone: Annotated[str, Query()] = "America/Santiago",
) -> AdminReportResponse:
    """Obtiene metricas agregadas sin datos personales sensibles."""

    filters = _build_filters(
        date_from=date_from,
        date_to=date_to,
        career=career,
        career_code=career_code,
        practice_type=practice_type,
        period=period,
        status=status,
        organization=organization,
        city=city,
        timezone=timezone,
    )

    return await _build_service(db).get_dashboard(filters, current_user)


@router.get("/export.csv")
async def export_admin_report_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(REPORT_ROLES))],
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    career: Annotated[str | None, Query()] = None,
    career_code: Annotated[str | None, Query()] = None,
    practice_type: Annotated[str | None, Query()] = None,
    period: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    organization: Annotated[str | None, Query()] = None,
    city: Annotated[str | None, Query()] = None,
    timezone: Annotated[str, Query()] = "America/Santiago",
) -> Response:
    """Exporta el reporte agregado en CSV sin RUT, correo ni documentos."""

    filters = _build_filters(
        date_from=date_from,
        date_to=date_to,
        career=career,
        career_code=career_code,
        practice_type=practice_type,
        period=period,
        status=status,
        organization=organization,
        city=city,
        timezone=timezone,
    )
    export = await _build_service(db).export_csv(filters, current_user)

    return Response(
        content=export.content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{export.filename}"',
        },
    )


@router.get("/export.pdf")
async def export_admin_report_pdf(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(REPORT_ROLES))],
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    career: Annotated[str | None, Query()] = None,
    career_code: Annotated[str | None, Query()] = None,
    practice_type: Annotated[str | None, Query()] = None,
    period: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    organization: Annotated[str | None, Query()] = None,
    city: Annotated[str | None, Query()] = None,
    timezone: Annotated[str, Query()] = "America/Santiago",
) -> Response:
    """Exporta un informe ejecutivo PDF sin datos personales."""

    filters = _build_filters(
        date_from=date_from,
        date_to=date_to,
        career=career,
        career_code=career_code,
        practice_type=practice_type,
        period=period,
        status=status,
        organization=organization,
        city=city,
        timezone=timezone,
    )
    export = await _build_service(db).export_pdf(filters, current_user)

    return Response(
        content=export.content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{export.filename}"',
        },
    )
