from datetime import date, datetime, UTC
from types import SimpleNamespace

import pytest

from app.modules.admin.schemas.admin_schema import (
    AdminUpdateInternshipSchoolInsuranceRequest,
    AdminUpdateSchoolInsuranceRequest,
    AdminUpdateStudentInternshipRequirementStatusRequest,
)
from app.modules.admin.services.admin_service import AdminService
from app.modules.internships.models.internship_model import SchoolInsuranceStatusEnum
from app.modules.internships.models.student_internship_requirement_model import (
    RegistrationRequirementType,
)


class FakeStudent:
    def __init__(
        self,
        student_id: int,
        email: str,
        first_name: str,
        last_name: str,
        rut: str,
        is_active: bool,
        degree: str | None = "Ingenieria Civil Informatica",
        cod_degree: str | None = "ICI",
    ) -> None:
        self.id = student_id
        self.email = email
        self.first_name = first_name
        self.last_name = last_name
        self.rut = rut
        self.is_active = is_active
        self.degree = degree
        self.cod_degree = cod_degree
        self.roles = [
            SimpleNamespace(role=SimpleNamespace(name="Estudiante")),
        ]


class FakeStatus:
    def __init__(
        self,
        status_id: int,
        title: str,
        description: str,
    ) -> None:
        self.id = status_id
        self.title = title
        self.description = description


class FakeInternship:
    def __init__(
        self,
        internship_id: int,
        student: FakeStudent | None,
        status: FakeStatus | None,
        is_cancelled: bool = False,
        cancelled_at: datetime | None = None,
        cancellation_reason: str | None = None,
    ) -> None:
        self.id = internship_id
        self.org_name = "Acme Chile"
        self.sector = "Tecnologia"
        self.address = "Av. Siempre Viva 123"
        self.city = "Temuco"
        self.org_phone = "+56912345678"
        self.web = "https://acme.example"
        self.supervisor_name = "Maria Supervisora"
        self.supervisor_profession = "Ingeniera Civil Informatica"
        self.supervisor_position = "Jefa de Desarrollo"
        self.supervisor_department = "Tecnologia"
        self.supervisor_email = "maria.supervisora@acme.example"
        self.supervisor_phone = "+56987654321"
        self.start_date = date(2026, 6, 1)
        self.end_date = date(2026, 8, 31)
        self.schedule = "09:00-18:00"
        self.days = "Lunes a viernes"
        self.modality = "Presencial"
        self.internship_address = "Av. Practica 456"
        self.act_description = "Desarrollo backend."
        self.ben_description = "Apoyo al equipo."
        self.amount = 120000
        self.upload_date = datetime(2026, 5, 15, 10, 0, tzinfo=UTC)
        self.status_id = None if status is None else status.id
        self.user_id = None if student is None else student.id
        self.internship_period = "Semestre"
        self.internship_type = "Práctica de Estudio I"
        self.student = student
        self.status = status
        self.is_cancelled = is_cancelled
        self.cancelled_at = cancelled_at
        self.cancellation_reason = cancellation_reason
        self.insurance_status = SchoolInsuranceStatusEnum.pending
        self.insurance_validated_by = None
        self.insurance_validated_at = None
        self.insurance_notes = None
        self.has_school_insurance = False


class FakeRegistrationRequirement:
    def __init__(
        self,
        requirement_id: int,
        user_id: int,
        is_completed: bool,
    ) -> None:
        self.id = requirement_id
        self.user_id = user_id
        self.requirement = RegistrationRequirementType.SCHOOL_INSURANCE
        self.is_completed = is_completed
        self.completed_at = None
        self.updated_by = None


class FakeAcademicRequirement:
    def __init__(self, requirement_id: int, user_id: int, status: str) -> None:
        self.id = requirement_id
        self.user_id = user_id
        self.type = "Práctica de Estudio I"
        self.status = status
        self.status_updated_at = None
        self.status_updated_by = None
        self.created_at = datetime(2026, 1, 1, 8, 0)
        self.updated_at = datetime(2026, 1, 1, 8, 0)


def _internship(
    internship_id: int = 10,
    student: FakeStudent | None = None,
    status: FakeStatus | None = None,
    is_cancelled: bool = False,
    cancelled_at: datetime | None = None,
    cancellation_reason: str | None = None,
) -> FakeInternship:
    return FakeInternship(
        internship_id=internship_id,
        student=student,
        status=status,
        is_cancelled=is_cancelled,
        cancelled_at=cancelled_at,
        cancellation_reason=cancellation_reason,
    )


class FakeAdminRepository:
    def __init__(self) -> None:
        self.students_count = 0
        self.internships_count = 0
        self.grouped_status_rows: list[tuple[str | None, int]] = []
        self.students: list[FakeStudent] = []
        self.internships: list[FakeInternship] = []
        self.internship_by_id: FakeInternship | None = None
        self.registration_requirements: list[FakeRegistrationRequirement] = []
        self.registration_requirement: FakeRegistrationRequirement | None = None
        self.saved_registration_requirement = None
        self.student_internship_requirement: FakeAcademicRequirement | None = None
        self.updated_student_internship_requirement = None
        self.updated_internship_school_insurance = None

    async def get_students_count(self) -> int:
        return self.students_count

    async def get_internships_count(self) -> int:
        return self.internships_count

    async def get_internships_grouped_by_status(self) -> list[tuple[str | None, int]]:
        return self.grouped_status_rows

    async def get_students(self) -> list[FakeStudent]:
        return self.students

    async def get_internships(self) -> list[FakeInternship]:
        return self.internships

    async def get_internship_by_id(self, internship_id: int) -> FakeInternship | None:
        return self.internship_by_id

    async def get_user_by_id(self, user_id: int) -> FakeStudent | None:
        return next(
            (student for student in self.students if student.id == user_id),
            None,
        )

    async def list_student_registration_requirements(
        self,
        student_id: int,
    ) -> list[FakeRegistrationRequirement]:
        return [
            requirement
            for requirement in self.registration_requirements
            if requirement.user_id == student_id
        ]

    async def get_student_registration_requirement(
        self,
        student_id: int,
        requirement: str,
    ) -> FakeRegistrationRequirement | None:
        return self.registration_requirement

    async def save_student_registration_requirement(self, requirement):
        if getattr(requirement, "id", None) is None:
            requirement.id = 1
        self.saved_registration_requirement = requirement
        return requirement

    async def get_student_internship_requirement(
        self,
        student_id: int,
        requirement_id: int,
    ) -> FakeAcademicRequirement | None:
        if self.student_internship_requirement is None:
            return None
        if (
            self.student_internship_requirement.user_id == student_id
            and self.student_internship_requirement.id == requirement_id
        ):
            return self.student_internship_requirement
        return None

    async def update_student_internship_requirement(self, requirement):
        self.updated_student_internship_requirement = requirement
        return requirement

    async def update_internship_school_insurance(
        self,
        internship,
        status,
        updated_by_user_id,
        notes,
    ):
        internship.insurance_status = status
        internship.insurance_validated_by = updated_by_user_id
        internship.insurance_validated_at = datetime(2026, 6, 21, 12, 0)
        internship.insurance_notes = notes
        internship.has_school_insurance = status == SchoolInsuranceStatusEnum.validated
        self.updated_internship_school_insurance = internship
        return internship


# Caso de prueba:
# cuando el repositorio entrega conteos globales validos y un desglose de
# practicas por estado, el servicio debe devolver el resumen administrativo
# conservando esos valores y respetando el orden recibido.
async def test_get_summary_returns_summary() -> None:
    repository = FakeAdminRepository()
    repository.students_count = 5
    repository.internships_count = 3
    repository.grouped_status_rows = [("En revision", 2), ("Aprobada", 1)]
    service = AdminService(db=None)
    service.repository = repository

    summary = await service.get_summary()

    assert summary.total_students == 5
    assert summary.total_internships == 3
    assert len(summary.internships_by_status) == 2
    assert summary.internships_by_status[0].status == "En revision"
    assert summary.internships_by_status[0].total == 2
    assert summary.internships_by_status[1].status == "Aprobada"
    assert summary.internships_by_status[1].total == 1


# Caso de prueba:
# cuando una practica llega sin estado desde el repositorio, el servicio no
# debe propagar un valor nulo al contrato HTTP; en su lugar debe traducirlo
# a la etiqueta legible "Sin estado".
async def test_get_summary_maps_missing_status() -> None:
    repository = FakeAdminRepository()
    repository.grouped_status_rows = [(None, 1)]
    service = AdminService(db=None)
    service.repository = repository
    summary = await service.get_summary()

    assert len(summary.internships_by_status) == 1
    assert summary.internships_by_status[0].status == "Sin estado"
    assert summary.internships_by_status[0].total == 1


# Caso de prueba:
# cuando el repositorio devuelve estudiantes validos, el servicio debe
# mapearlos al schema administrativo sin perder campos relevantes del
# usuario, como identificador, correo y estado de activacion.
async def test_get_students_maps_students() -> None:
    repository = FakeAdminRepository()
    repository.students = [
        FakeStudent(
            student_id=7,
            email="ana@example.com",
            first_name="Ana",
            last_name="Lopez",
            rut="12.345.678-9",
            is_active=True,
        ),
    ]
    service = AdminService(db=None)
    service.repository = repository

    students = await service.get_students()

    assert len(students) == 1
    assert students[0].id == 7
    assert students[0].email == "ana@example.com"
    assert students[0].first_name == "Ana"
    assert students[0].last_name == "Lopez"
    assert students[0].rut == "12.345.678-9"
    assert students[0].is_active is True
    assert students[0].degree == "Ingenieria Civil Informatica"
    assert students[0].cod_degree == "ICI"


async def test_update_requirement_status_uses_naive_timestamp() -> None:
    repository = FakeAdminRepository()
    student = FakeStudent(
        student_id=7,
        email="ana@example.com",
        first_name="Ana",
        last_name="Lopez",
        rut="12.345.678-9",
        is_active=True,
    )
    repository.students = [student]
    repository.student_internship_requirement = FakeAcademicRequirement(
        requirement_id=3,
        user_id=student.id,
        status="Pendiente",
    )
    service = AdminService(db=None)
    service.repository = repository

    updated = await service.update_student_internship_requirement_status(
        student_id=student.id,
        requirement_id=3,
        payload=AdminUpdateStudentInternshipRequirementStatusRequest(
            status="Habilitada",
        ),
        updated_by_user_id=99,
    )

    assert updated is not None
    assert updated.status == "Habilitada"
    assert repository.updated_student_internship_requirement.status_updated_by == 99
    assert repository.updated_student_internship_requirement.status_updated_at.tzinfo is None


# Caso de prueba:
# cuando una practica incluye estudiante y estado relacionados, el servicio
# debe incluir ambos bloques anidados en el item administrativo para que el
# controller pueda responder sin reconstruir relaciones manualmente.
async def test_get_internships_maps_related_data() -> None:
    repository = FakeAdminRepository()
    student = FakeStudent(
        student_id=1,
        email="student@example.com",
        first_name="Juan",
        last_name="Perez",
        rut="12.345.678-9",
        is_active=True,
    )
    status = FakeStatus(
        status_id=1,
        title="En revision",
        description="Practica en revision administrativa.",
    )
    repository.internships = [_internship(student=student, status=status)]
    service = AdminService(db=None)
    service.repository = repository

    internships = await service.get_internships()

    assert len(internships) == 1
    assert internships[0].id == 10
    assert internships[0].student is not None
    assert internships[0].student.email == "student@example.com"
    assert internships[0].student.degree == "Ingenieria Civil Informatica"
    assert internships[0].student.cod_degree == "ICI"
    assert internships[0].internship_type == "Práctica de Estudio I"
    assert internships[0].status is not None
    assert internships[0].status.title == "En revision"
    assert internships[0].is_cancelled is False


async def test_get_internships_marks_cancelled_practices() -> None:
    repository = FakeAdminRepository()
    student = FakeStudent(
        student_id=1,
        email="student@example.com",
        first_name="Juan",
        last_name="Perez",
        rut="12.345.678-9",
        is_active=True,
    )
    repository.internships = [
        _internship(
            student=student,
            status=FakeStatus(
                status_id=1,
                title="Pendiente",
                description="Pendiente.",
            ),
            is_cancelled=True,
        ),
    ]
    service = AdminService(db=None)
    service.repository = repository

    internships = await service.get_internships()

    assert len(internships) == 1
    assert internships[0].status is not None
    assert internships[0].status.title == "Pendiente"
    assert internships[0].is_cancelled is True


# Caso de prueba:
# cuando una practica no tiene estado relacionado, el servicio debe seguir
# devolviendo el item de la lista. La ausencia del estado no debe romper el
# mapeo; simplemente el bloque `status` debe quedar en `None`.
async def test_get_internships_allows_none_status() -> None:
    repository = FakeAdminRepository()
    student = FakeStudent(
        student_id=1,
        email="student@example.com",
        first_name="Juan",
        last_name="Perez",
        rut="12.345.678-9",
        is_active=True,
    )
    repository.internships = [_internship(student=student, status=None)]
    service = AdminService(db=None)
    service.repository = repository

    internships = await service.get_internships()

    assert len(internships) == 1
    assert internships[0].student is not None
    assert internships[0].status is None


# Caso de prueba:
# el dashboard del coordinador consume `/admin/internships?status=...`.
# El servicio debe filtrar usando estados normalizados sin exigir que el
# frontend consulte `/internships`.
async def test_get_internships_filters_by_dashboard_status() -> None:
    repository = FakeAdminRepository()
    student = FakeStudent(
        student_id=1,
        email="student@example.com",
        first_name="Juan",
        last_name="Perez",
        rut="12.345.678-9",
        is_active=True,
    )
    repository.internships = [
        _internship(
            internship_id=1,
            student=student,
            status=FakeStatus(
                status_id=1,
                title="Pendiente",
                description="Pendiente.",
            ),
        ),
        _internship(
            internship_id=2,
            student=student,
            status=FakeStatus(
                status_id=2,
                title="En revisión",
                description="En revisión administrativa.",
            ),
        ),
        _internship(
            internship_id=3,
            student=student,
            status=FakeStatus(
                status_id=3,
                title="En revisión DIRAE",
                description="Derivada a DIRAE.",
            ),
        ),
        _internship(
            internship_id=4,
            student=student,
            status=FakeStatus(
                status_id=4,
                title="Aprobada",
                description="Aprobada.",
            ),
        ),
        _internship(
            internship_id=5,
            student=student,
            status=None,
        ),
        _internship(
            internship_id=6,
            student=student,
            status=FakeStatus(
                status_id=1,
                title="Pendiente",
                description="Pendiente.",
            ),
            is_cancelled=True,
        ),
    ]
    service = AdminService(db=None)
    service.repository = repository

    submitted = await service.get_internships(status_filter="submitted")
    in_review = await service.get_internships(status_filter="in_review")
    approved = await service.get_internships(status_filter="approved")

    assert [internship.id for internship in submitted] == [1, 5]
    assert [internship.id for internship in in_review] == [2, 3]
    assert [internship.id for internship in approved] == [4]


# Caso de prueba:
# cuando la practica existe, el servicio debe devolver el detalle completo
# y mantener disponibles las relaciones necesarias para que el controller
# pueda responder el recurso administrativo sin transformaciones extra.
async def test_get_internship_detail_returns_detail() -> None:
    repository = FakeAdminRepository()
    student = FakeStudent(
        student_id=1,
        email="student@example.com",
        first_name="Juan",
        last_name="Perez",
        rut="12.345.678-9",
        is_active=True,
    )
    status = FakeStatus(
        status_id=1,
        title="Aprobada",
        description="Practica aprobada por el encargado.",
    )
    repository.internship_by_id = _internship(
        internship_id=21,
        student=student,
        status=status,
    )
    service = AdminService(db=None)
    service.repository = repository

    internship = await service.get_internship_detail(internship_id=21)

    assert internship is not None
    assert internship.id == 21
    assert internship.org_name == "Acme Chile"
    assert internship.student is not None
    assert internship.student.first_name == "Juan"
    assert internship.status is not None
    assert internship.status.title == "Aprobada"
    assert internship.internship_type == "Práctica de Estudio I"
    assert internship.internship_period == "Semestre"
    assert internship.supervisor_name == "Maria Supervisora"
    assert internship.supervisor_email == "maria.supervisora@acme.example"
    assert "dirae_status" not in internship.model_dump()
    assert internship.is_cancelled is False
    assert internship.cancelled_at is None
    assert internship.cancellation_reason is None


# Caso de prueba:
# cuando la practica solicitada no existe, el servicio no debe inventar una
# respuesta vacia ni lanzar una excepcion HTTP. Debe devolver `None` para
# que el controller traduzca ese caso a un `404`.
async def test_get_internship_detail_returns_none() -> None:
    repository = FakeAdminRepository()
    repository.internship_by_id = None
    service = AdminService(db=None)
    service.repository = repository

    internship = await service.get_internship_detail(internship_id=404)

    assert internship is None


async def test_update_internship_school_insurance_validates_request() -> None:
    repository = FakeAdminRepository()
    student = FakeStudent(
        student_id=7,
        email="ana@example.com",
        first_name="Ana",
        last_name="Lopez",
        rut="12.345.678-9",
        is_active=True,
    )
    repository.internship_by_id = _internship(
        internship_id=15,
        student=student,
        status=FakeStatus(1, "Pendiente", "Pendiente"),
    )
    service = AdminService(db=None)
    service.repository = repository

    result = await service.update_internship_school_insurance(
        internship_id=15,
        payload=AdminUpdateInternshipSchoolInsuranceRequest(
            status="validated",
            notes="Seguro validado para esta solicitud.",
        ),
        updated_by_user_id=20,
    )

    assert result is not None
    assert result.insurance_status == SchoolInsuranceStatusEnum.validated
    assert result.insurance_validated_by == 20
    assert result.insurance_notes == "Seguro validado para esta solicitud."
    assert repository.updated_internship_school_insurance.has_school_insurance is True


async def test_update_internship_school_insurance_rejects_cancelled_practice() -> None:
    repository = FakeAdminRepository()
    student = FakeStudent(
        student_id=7,
        email="ana@example.com",
        first_name="Ana",
        last_name="Lopez",
        rut="12.345.678-9",
        is_active=True,
    )
    repository.internship_by_id = _internship(
        internship_id=15,
        student=student,
        status=FakeStatus(1, "Pendiente", "Pendiente"),
        is_cancelled=True,
    )
    service = AdminService(db=None)
    service.repository = repository

    with pytest.raises(ValueError, match="solicitud anulada"):
        await service.update_internship_school_insurance(
            internship_id=15,
            payload=AdminUpdateInternshipSchoolInsuranceRequest(
                status="validated",
                notes="Seguro validado para esta solicitud.",
            ),
            updated_by_user_id=20,
        )

    assert repository.updated_internship_school_insurance is None


async def test_get_student_registration_requirements_returns_institutional_data() -> None:
    repository = FakeAdminRepository()
    repository.students = [
        FakeStudent(
            student_id=7,
            email="ana@example.com",
            first_name="Ana",
            last_name="Lopez",
            rut="12.345.678-9",
            is_active=True,
        ),
    ]
    repository.registration_requirements = [
        FakeRegistrationRequirement(
            requirement_id=3,
            user_id=7,
            is_completed=True,
        ),
    ]
    service = AdminService(db=None)
    service.repository = repository

    requirements = await service.get_student_registration_requirements(7)

    assert requirements is not None
    assert len(requirements) == 1
    assert requirements[0].requirement == "school_insurance"
    assert requirements[0].is_completed is True


async def test_update_school_insurance_creates_missing_requirement() -> None:
    repository = FakeAdminRepository()
    repository.students = [
        FakeStudent(
            student_id=7,
            email="ana@example.com",
            first_name="Ana",
            last_name="Lopez",
            rut="12.345.678-9",
            is_active=True,
        ),
    ]
    service = AdminService(db=None)
    service.repository = repository

    result = await service.update_school_insurance_requirement(
        student_id=7,
        payload=AdminUpdateSchoolInsuranceRequest(is_completed=True),
        updated_by_user_id=20,
    )

    assert result is not None
    assert result.requirement == "school_insurance"
    assert result.is_completed is True
    assert result.completed_at is not None
    assert result.updated_by == 20


async def test_update_school_insurance_clears_completion_when_revoked() -> None:
    repository = FakeAdminRepository()
    repository.students = [
        FakeStudent(
            student_id=7,
            email="ana@example.com",
            first_name="Ana",
            last_name="Lopez",
            rut="12.345.678-9",
            is_active=True,
        ),
    ]
    requirement = FakeRegistrationRequirement(
        requirement_id=3,
        user_id=7,
        is_completed=True,
    )
    requirement.completed_at = datetime(2026, 6, 1, tzinfo=UTC)
    repository.registration_requirement = requirement
    service = AdminService(db=None)
    service.repository = repository

    result = await service.update_school_insurance_requirement(
        student_id=7,
        payload=AdminUpdateSchoolInsuranceRequest(is_completed=False),
        updated_by_user_id=20,
    )

    assert result is not None
    assert result.is_completed is False
    assert result.completed_at is None
    assert result.updated_by == 20


async def test_update_school_insurance_returns_none_for_non_student() -> None:
    repository = FakeAdminRepository()
    user = FakeStudent(
        student_id=7,
        email="director@example.com",
        first_name="Dora",
        last_name="Directora",
        rut="12.345.678-9",
        is_active=True,
    )
    user.roles = [
        SimpleNamespace(role=SimpleNamespace(name="Director de carrera")),
    ]
    repository.students = [user]
    service = AdminService(db=None)
    service.repository = repository

    result = await service.update_school_insurance_requirement(
        student_id=7,
        payload=AdminUpdateSchoolInsuranceRequest(is_completed=True),
        updated_by_user_id=20,
    )

    assert result is None
