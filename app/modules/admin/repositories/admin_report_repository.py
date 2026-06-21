"""Consultas agregadas para reportes administrativos y FICA."""

from datetime import date

from sqlalchemy import Date, Integer, Select, String, and_, cast, desc, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.schemas.admin_report_schema import AdminReportFilters
from app.modules.auth.models.user_model import User
from app.modules.documents.models.document_model import (
    Document,
    DocumentStatusEnum,
    DocumentType,
)
from app.modules.internships.models.current_state_model import CurrentState
from app.modules.internships.models.internship_exception_model import (
    ExceptableRule,
    InternshipException,
)
from app.modules.internships.models.internship_model import (
    CompletionStatusEnum,
    Internship,
    SchoolInsuranceStatusEnum,
)
from app.modules.internships.models.internship_status_history_model import (
    InternshipStatusHistory,
)
from app.modules.supervisor_evaluations.models.supervisor_evaluation_model import (
    SupervisorEvaluation,
)
from app.modules.self_evaluations.models.self_evaluation_model import (
    SelfEvaluation,
    SelfEvaluationStatusEnum,
)

APPROVED_STATUS = "Aprobada"
REJECTED_STATUSES = ("Rechazada", "Reprobada")
UNKNOWN_VALUE = "Sin dato"


class AdminReportRepository:
    """Ejecuta agregaciones sin cargar practicas completas en memoria."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def count_internships(self, filters: AdminReportFilters) -> int:
        query = self._internship_query(filters, func.count(Internship.id))
        result = await self.db.execute(query)

        return result.scalar_one() or 0

    async def count_students(self, filters: AdminReportFilters) -> int:
        query = self._internship_query(filters, func.count(distinct(Internship.user_id)))
        result = await self.db.execute(query)

        return result.scalar_one() or 0

    async def count_cancelled(self, filters: AdminReportFilters) -> int:
        query = self._internship_query(filters, func.count(Internship.id)).where(
            Internship.is_cancelled.is_(True),
        )
        result = await self.db.execute(query)

        return result.scalar_one() or 0

    async def grouped_by_status(self, filters: AdminReportFilters) -> list[tuple[str, int]]:
        status_name = func.coalesce(cast(CurrentState.title, String), UNKNOWN_VALUE)
        query = (
            self._internship_query(filters, status_name, func.count(Internship.id))
            .group_by(status_name)
            .order_by(status_name.asc())
        )
        result = await self.db.execute(query)

        return [(name, total) for name, total in result.all()]

    async def grouped_by_career(self, filters: AdminReportFilters) -> list[tuple[str, int]]:
        career_name = func.coalesce(User.degree, UNKNOWN_VALUE)
        query = (
            self._internship_query(filters, career_name, func.count(Internship.id))
            .group_by(career_name)
            .order_by(career_name.asc())
        )
        result = await self.db.execute(query)

        return [(name, total) for name, total in result.all()]

    async def grouped_by_practice_type(
        self,
        filters: AdminReportFilters,
    ) -> list[tuple[str, int]]:
        practice_type = func.coalesce(cast(Internship.internship_type, String), UNKNOWN_VALUE)
        query = (
            self._internship_query(filters, practice_type, func.count(Internship.id))
            .group_by(practice_type)
            .order_by(practice_type.asc())
        )
        result = await self.db.execute(query)

        return [(name, total) for name, total in result.all()]

    async def grouped_by_period(self, filters: AdminReportFilters) -> list[tuple[str, int]]:
        period = func.coalesce(cast(Internship.internship_period, String), UNKNOWN_VALUE)
        query = (
            self._internship_query(filters, period, func.count(Internship.id))
            .group_by(period)
            .order_by(period.asc())
        )
        result = await self.db.execute(query)

        return [(name, total) for name, total in result.all()]

    async def grouped_by_city(self, filters: AdminReportFilters) -> list[tuple[str, int]]:
        city = func.coalesce(Internship.city, UNKNOWN_VALUE)
        query = (
            self._internship_query(filters, city, func.count(Internship.id))
            .group_by(city)
            .order_by(desc(func.count(Internship.id)), city.asc())
        )
        result = await self.db.execute(query)

        return [(name, total) for name, total in result.all()]

    async def count_by_status_titles(
        self,
        filters: AdminReportFilters,
        status_titles: tuple[str, ...],
    ) -> int:
        query = self._internship_query(filters, func.count(Internship.id)).where(
            CurrentState.title.in_(status_titles),
        )
        result = await self.db.execute(query)

        return result.scalar_one() or 0

    async def time_to_status(
        self,
        filters: AdminReportFilters,
        status_titles: tuple[str, ...],
    ) -> tuple[float | None, float | None, int]:
        filtered = self._filtered_internship_ids(filters).subquery()
        first_transition = (
            select(
                InternshipStatusHistory.internship_id.label("internship_id"),
                func.min(InternshipStatusHistory.changed_at).label("changed_at"),
            )
            .select_from(InternshipStatusHistory)
            .join(
                CurrentState,
                CurrentState.id == InternshipStatusHistory.new_status_id,
            )
            .where(CurrentState.title.in_(status_titles))
            .group_by(InternshipStatusHistory.internship_id)
            .subquery()
        )
        days_expr = func.extract(
            "epoch",
            first_transition.c.changed_at - filtered.c.upload_date,
        ) / 86400.0
        query = (
            select(
                func.avg(days_expr),
                func.percentile_cont(0.5).within_group(days_expr),
                func.count(first_transition.c.internship_id),
            )
            .select_from(filtered)
            .join(first_transition, first_transition.c.internship_id == filtered.c.id)
        )
        result = await self.db.execute(query)
        average_days, median_days, samples = result.one()

        return average_days, median_days, samples or 0

    async def recurrent_organizations(
        self,
        filters: AdminReportFilters,
        limit: int = 10,
    ) -> list[tuple[str, str, int, int, int, int]]:
        normalized_name = func.lower(func.trim(Internship.org_name))
        query = (
            self._internship_query(
                filters,
                normalized_name.label("normalized_name"),
                func.min(Internship.org_name).label("display_name"),
                func.count(Internship.id).label("total"),
                func.sum(cast(CurrentState.title == APPROVED_STATUS, Integer)).label("approved"),
                func.sum(cast(CurrentState.title.in_(REJECTED_STATUSES), Integer)).label(
                    "rejected",
                ),
                func.sum(cast(Internship.is_cancelled.is_(True), Integer)).label(
                    "cancelled",
                ),
            )
            .group_by(normalized_name)
            .having(func.count(Internship.id) > 1)
            .order_by(desc(func.count(Internship.id)), normalized_name.asc())
            .limit(limit)
        )
        result = await self.db.execute(query)

        return [tuple(row) for row in result.all()]

    async def required_document_type_count(self) -> int:
        query = select(func.count(DocumentType.id)).where(
            DocumentType.is_required.is_(True),
            DocumentType.is_active.is_(True),
        )
        result = await self.db.execute(query)

        return result.scalar_one() or 0

    async def document_summary(
        self,
        filters: AdminReportFilters,
        required_type_count: int,
    ) -> tuple[int, int, int, int]:
        observed = await self._count_document_packages_by_status(
            filters,
            DocumentStatusEnum.observed,
        )
        if required_type_count == 0:
            return 0, observed, 0, 0

        approved_required_counts = (
            self._document_query(
                filters,
                Document.internship_id.label("internship_id"),
                func.count(distinct(Document.type_id)).label("approved_required"),
            )
            .join(DocumentType, DocumentType.id == Document.type_id)
            .where(
                DocumentType.is_required.is_(True),
                DocumentType.is_active.is_(True),
                Document.status == DocumentStatusEnum.approved,
                Document.deleted_at.is_(None),
            )
            .group_by(Document.internship_id)
            .subquery()
        )
        complete_query = select(func.count()).select_from(approved_required_counts).where(
            approved_required_counts.c.approved_required >= required_type_count,
        )
        complete_result = await self.db.execute(complete_query)
        complete = complete_result.scalar_one() or 0

        total = await self.count_internships(filters)
        missing = max(total - complete, 0)

        return complete, observed, missing, complete

    async def supervisor_evaluation_counts(
        self,
        filters: AdminReportFilters,
    ) -> tuple[int, int]:
        total = await self.count_internships(filters)
        query = (
            self._evaluation_query(filters, func.count(distinct(SupervisorEvaluation.id)))
            .where(SupervisorEvaluation.status == "submitted")
        )
        result = await self.db.execute(query)
        submitted = result.scalar_one() or 0

        return submitted, max(total - submitted, 0)

    async def self_evaluation_counts(
        self,
        filters: AdminReportFilters,
    ) -> tuple[int, int]:
        total = await self.count_internships(filters)
        query = (
            self._self_evaluation_query(
                filters,
                func.count(distinct(SelfEvaluation.id)),
            )
            .where(SelfEvaluation.status == SelfEvaluationStatusEnum.submitted)
        )
        result = await self.db.execute(query)
        submitted = result.scalar_one() or 0

        return submitted, max(total - submitted, 0)

    async def finalized_internship_count(self, filters: AdminReportFilters) -> int:
        query = self._internship_query(filters, func.count(Internship.id)).where(
            Internship.completion_status == CompletionStatusEnum.finalized,
        )
        result = await self.db.execute(query)

        return result.scalar_one() or 0

    async def summer_without_school_insurance(self, filters: AdminReportFilters) -> int:
        exception_subquery = (
            select(InternshipException.internship_id)
            .where(InternshipException.rule == ExceptableRule.SCHOOL_INSURANCE)
            .subquery()
        )
        query = (
            self._internship_query(filters, func.count(Internship.id))
            .outerjoin(
                exception_subquery,
                exception_subquery.c.internship_id == Internship.id,
            )
            .where(
                Internship.internship_period == "Verano",
                Internship.insurance_status.not_in(
                    (
                        SchoolInsuranceStatusEnum.validated,
                        SchoolInsuranceStatusEnum.exception_authorized,
                        SchoolInsuranceStatusEnum.not_applicable,
                    )
                ),
                exception_subquery.c.internship_id.is_(None),
            )
        )
        result = await self.db.execute(query)

        return result.scalar_one() or 0

    async def overdue_active_internships(
        self,
        filters: AdminReportFilters,
        today: date,
    ) -> int:
        query = self._internship_query(filters, func.count(Internship.id)).where(
            Internship.end_date < today,
            Internship.is_cancelled.is_(False),
            CurrentState.title.not_in((APPROVED_STATUS, *REJECTED_STATUSES)),
        )
        result = await self.db.execute(query)

        return result.scalar_one() or 0

    def _internship_query(self, filters: AdminReportFilters, *columns) -> Select:
        query = (
            select(*columns)
            .select_from(Internship)
            .outerjoin(User, User.id == Internship.user_id)
            .outerjoin(CurrentState, CurrentState.id == Internship.status_id)
        )

        return query.where(*self._filter_conditions(filters))

    def _filtered_internship_ids(self, filters: AdminReportFilters) -> Select:
        return self._internship_query(
            filters,
            Internship.id.label("id"),
            Internship.upload_date.label("upload_date"),
        )

    def _document_query(self, filters: AdminReportFilters, *columns) -> Select:
        return (
            select(*columns)
            .select_from(Document)
            .join(Internship, Internship.id == Document.internship_id)
            .outerjoin(User, User.id == Internship.user_id)
            .outerjoin(CurrentState, CurrentState.id == Internship.status_id)
            .where(*self._filter_conditions(filters))
        )

    def _evaluation_query(self, filters: AdminReportFilters, *columns) -> Select:
        return (
            select(*columns)
            .select_from(SupervisorEvaluation)
            .join(Internship, Internship.id == SupervisorEvaluation.internship_id)
            .outerjoin(User, User.id == Internship.user_id)
            .outerjoin(CurrentState, CurrentState.id == Internship.status_id)
            .where(*self._filter_conditions(filters))
        )

    def _self_evaluation_query(self, filters: AdminReportFilters, *columns) -> Select:
        return (
            select(*columns)
            .select_from(SelfEvaluation)
            .join(Internship, Internship.id == SelfEvaluation.internship_id)
            .outerjoin(User, User.id == Internship.user_id)
            .outerjoin(CurrentState, CurrentState.id == Internship.status_id)
            .where(*self._filter_conditions(filters))
        )

    async def _count_document_packages_by_status(
        self,
        filters: AdminReportFilters,
        status: DocumentStatusEnum,
    ) -> int:
        query = self._document_query(
            filters,
            func.count(distinct(Document.internship_id)),
        ).where(Document.status == status, Document.deleted_at.is_(None))
        result = await self.db.execute(query)

        return result.scalar_one() or 0

    def _filter_conditions(self, filters: AdminReportFilters) -> list:
        conditions = []

        if filters.date_from is not None:
            conditions.append(cast(Internship.upload_date, Date) >= filters.date_from)
        if filters.date_to is not None:
            conditions.append(cast(Internship.upload_date, Date) <= filters.date_to)
        if filters.career:
            conditions.append(User.degree.ilike(f"%{filters.career}%"))
        if filters.career_code:
            conditions.append(User.cod_degree == filters.career_code)
        if filters.practice_type:
            conditions.append(Internship.internship_type == filters.practice_type)
        if filters.period:
            conditions.append(Internship.internship_period == filters.period)
        if filters.status:
            conditions.append(CurrentState.title == filters.status)
        if filters.organization:
            conditions.append(Internship.org_name.ilike(f"%{filters.organization}%"))
        if filters.city:
            conditions.append(Internship.city.ilike(f"%{filters.city}%"))

        return [and_(*conditions)] if conditions else []
