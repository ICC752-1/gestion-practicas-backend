from datetime import date, datetime, UTC
from types import SimpleNamespace

import pytest

from app.modules.admin.schemas.admin_schema import (
    AdminUpdateSchoolInsuranceRequest,
    AdminUpdateStudentInternshipRequirementStatusRequest,
)
from app.modules.admin.services.admin_service import AdminService
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
    ) -> None:
        self.id = student_id
        self.email = email
        self.first_name = first_name
        self.last_name = last_name
        self.rut = rut
        self.is_active = is_active
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
    ) -> None:
        self.id = internship_id
        self.org_name = "Acme Chile"
        self.sector = "Tecnologia"
        self.address = "Av. Siempre Viva 123"
        self.city = "Temuco"
        self.org_phone = "+56912345678"
        self.web = "https://acme.example"
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
        self.student = student
        self.status = status


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


class FakeStudentInternshipRequirement:
    def __init__(
        self,
        requirement_id: int,
        user_id: int,
        requirement_type: str,
        status: str,
    ) -> None:
        self.id = requirement_id
        self.user_id = user_id
        self.type = requirement_type
        self.status = status
        self.status_updated_at = None
        self.status_updated_by = None
        self.created_at = datetime(2026, 5, 1, tzinfo=UTC)
        self.updated_at = datetime(2026, 5, 1, tzinfo=UTC)


class FakeNotificationService:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.notifications = []

    async def create_and_dispatch(self, notification):
        self.notifications.append(notification)
        if self.should_fail:
            raise RuntimeError("notification failed")
        return notification


def _internship(
    internship_id: int = 10,
    student: FakeStudent | None = None,
    status: FakeStatus | None = None,
) -> FakeInternship:
    return FakeInternship(
        internship_id=internship_id,
        student=student,
        status=status,
    )


class FakeAdminRepository:
    def __init__(self) -> None:
        self.students_count = 0
        self.internships_count = 0
        self.grouped_status_rows: list[tuple[str | None, int]] = []
        self.students: list[FakeStudent] = []
        self.internships: list[FakeInternship] = []
        self.internship_by_id: FakeInternship | None = None
        self.student_internship_requirements: list[
            FakeStudentInternshipRequirement
        ] = []
        self.student_internship_requirement: (
            FakeStudentInternshipRequirement | None
        ) = None
        self.updated_student_internship_requirement = None
        self.registration_requirements: list[FakeRegistrationRequirement] = []
        self.registration_requirement: FakeRegistrationRequirement | None = None
        self.saved_registration_requirement = None

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

    async def list_student_internship_requirements(
        self,
        student_id: int,
    ) -> list[FakeStudentInternshipRequirement]:
        return [
            requirement
            for requirement in self.student_internship_requirements
            if requirement.user_id == student_id
        ]

    async def get_student_internship_requirement(
        self,
        student_id: int,
        requirement_id: int,
    ) -> FakeStudentInternshipRequirement | None:
        requirement = self.student_internship_requirement
        if requirement is None:
            return None
        if requirement.user_id != student_id or requirement.id != requirement_id:
            return None
        return requirement

    async def update_student_internship_requirement(self, requirement):
        self.updated_student_internship_requirement = requirement
        return requirement

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
    assert internships[0].status is not None
    assert internships[0].status.title == "En revision"


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


async def test_get_student_internship_requirements_maps_requirements() -> None:
    repository = FakeAdminRepository()
    repository.student_internship_requirements = [
        FakeStudentInternshipRequirement(
            requirement_id=3,
            user_id=7,
            requirement_type="Práctica de Estudio I",
            status="Habilitada",
        ),
    ]
    service = AdminService(db=None)
    service.repository = repository

    requirements = await service.get_student_internship_requirements(7)

    assert len(requirements) == 1
    assert requirements[0].id == 3
    assert requirements[0].user_id == 7
    assert requirements[0].type == "Práctica de Estudio I"
    assert requirements[0].status == "Habilitada"


@pytest.mark.parametrize(
    "current_status,new_status",
    [
        ("Pendiente", "Habilitada"),
        ("Habilitada", "En revisión"),
        ("En revisión", "Aprobada"),
        ("En revisión", "Rechazada"),
        ("Rechazada", "Habilitada"),
    ],
)
async def test_update_student_internship_requirement_accepts_valid_transition(
    current_status,
    new_status,
) -> None:
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
    repository.student_internship_requirement = FakeStudentInternshipRequirement(
        requirement_id=3,
        user_id=7,
        requirement_type="Práctica de Estudio I",
        status=current_status,
    )
    service = AdminService(db=None)
    service.repository = repository

    result = await service.update_student_internship_requirement_status(
        student_id=7,
        requirement_id=3,
        payload=AdminUpdateStudentInternshipRequirementStatusRequest(
            status=new_status,
        ),
        updated_by_user_id=20,
    )

    assert result is not None
    assert result.status == new_status
    assert result.status_updated_at is not None
    assert result.status_updated_by == 20


@pytest.mark.parametrize(
    "current_status,new_status",
    [
        ("Pendiente", "Aprobada"),
        ("Aprobada", "Rechazada"),
        ("Habilitada", "Aprobada"),
    ],
)
async def test_update_student_internship_requirement_rejects_invalid_transition(
    current_status,
    new_status,
) -> None:
    repository = FakeAdminRepository()
    repository.student_internship_requirement = FakeStudentInternshipRequirement(
        requirement_id=3,
        user_id=7,
        requirement_type="Práctica de Estudio I",
        status=current_status,
    )
    service = AdminService(db=None)
    service.repository = repository

    with pytest.raises(ValueError):
        await service.update_student_internship_requirement_status(
            student_id=7,
            requirement_id=3,
            payload=AdminUpdateStudentInternshipRequirementStatusRequest(
                status=new_status,
            ),
            updated_by_user_id=20,
        )


async def test_update_student_internship_requirement_allows_same_status() -> None:
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
    repository.student_internship_requirement = FakeStudentInternshipRequirement(
        requirement_id=3,
        user_id=7,
        requirement_type="Práctica de Estudio I",
        status="Habilitada",
    )
    service = AdminService(db=None)
    service.repository = repository

    result = await service.update_student_internship_requirement_status(
        student_id=7,
        requirement_id=3,
        payload=AdminUpdateStudentInternshipRequirementStatusRequest(
            status="Habilitada",
        ),
        updated_by_user_id=20,
    )

    assert result is not None
    assert result.status == "Habilitada"
    assert result.status_updated_by == 20


async def test_update_student_internship_requirement_returns_none_when_missing() -> None:
    repository = FakeAdminRepository()
    repository.student_internship_requirement = None
    service = AdminService(db=None)
    service.repository = repository

    result = await service.update_student_internship_requirement_status(
        student_id=7,
        requirement_id=404,
        payload=AdminUpdateStudentInternshipRequirementStatusRequest(
            status="Habilitada",
        ),
        updated_by_user_id=20,
    )

    assert result is None


async def test_update_student_internship_requirement_dispatches_notification() -> None:
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
    repository.student_internship_requirement = FakeStudentInternshipRequirement(
        requirement_id=3,
        user_id=7,
        requirement_type="Práctica de Estudio I",
        status="Pendiente",
    )
    notification_service = FakeNotificationService()
    service = AdminService(db=None, notification_service=notification_service)
    service.repository = repository

    result = await service.update_student_internship_requirement_status(
        student_id=7,
        requirement_id=3,
        payload=AdminUpdateStudentInternshipRequirementStatusRequest(
            status="Habilitada",
        ),
        updated_by_user_id=20,
    )

    assert result is not None
    assert len(notification_service.notifications) == 1
    notification = notification_service.notifications[0]
    assert notification.recipient_user_id == 7
    assert notification.recipient_email == "ana@example.com"
    assert notification.payload["requirement_id"] == 3
    assert notification.payload["new_status"] == "Habilitada"
    assert notification.payload["previous_status"] == "Pendiente"


async def test_update_student_internship_requirement_ignores_notification_failure() -> None:
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
    repository.student_internship_requirement = FakeStudentInternshipRequirement(
        requirement_id=3,
        user_id=7,
        requirement_type="Práctica de Estudio I",
        status="Pendiente",
    )
    service = AdminService(
        db=None,
        notification_service=FakeNotificationService(should_fail=True),
    )
    service.repository = repository

    result = await service.update_student_internship_requirement_status(
        student_id=7,
        requirement_id=3,
        payload=AdminUpdateStudentInternshipRequirementStatusRequest(
            status="Habilitada",
        ),
        updated_by_user_id=20,
    )

    assert result is not None
    assert result.status == "Habilitada"


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
