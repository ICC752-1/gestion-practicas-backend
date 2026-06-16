"""Tests de integración de eventos de notificación entre servicios.

Estos casos ejercitan los servicios de negocio que emiten eventos y el
``NotificationService`` real en modo ``simulated`` usando repositorios en memoria.
No validan transporte SMTP ni base de datos; validan que el flujo de dominio
construye y persiste las notificaciones esperadas.
"""

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from app.modules.documents.models.document_model import DocumentStatusEnum
from app.modules.documents.services.document_service import DocumentService
from app.modules.internships.models.internship_model import (
    PracticePeriodEnum,
    PracticeTypeEnum,
)
from app.modules.internships.schemas.internship_schema import InternshipCreateRequest
from app.modules.internships.services.internship_service import InternshipService
from app.modules.notifications.models.notification_model import (
    NotificationEventTypeEnum,
    NotificationStatusEnum,
)
from app.modules.notifications.services.notification_service import NotificationService


def _notification_config() -> SimpleNamespace:
    return SimpleNamespace(
        NOTIFICATION_MODE="simulated",
        MAIL_USERNAME="test@example.com",
        MAIL_PASSWORD="password",
        MAIL_FROM="test@example.com",
        MAIL_PORT=1025,
        MAIL_SERVER="localhost",
        MAIL_STARTTLS=False,
        MAIL_SSL_TLS=False,
    )


def _document_config(tmp_path) -> SimpleNamespace:
    return SimpleNamespace(
        DOCUMENT_STORAGE_DIR=str(tmp_path),
        DOCUMENT_MAX_BYTES=1024,
        DOCUMENT_ALLOWED_EXTENSIONS="pdf,docx,jpg,png,zip",
    )


def _role(name: str) -> SimpleNamespace:
    return SimpleNamespace(role=SimpleNamespace(name=name))


def _user(user_id: int, email: str, *roles: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        email=email,
        roles=[_role(role_name) for role_name in roles],
    )


def _state(state_id: int, title: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=state_id,
        title=title,
        description=f"Estado {title}",
    )


def _internship_payload() -> InternshipCreateRequest:
    return InternshipCreateRequest(
        org_name="Acme Chile",
        sector="Tecnologia",
        address="Av. Siempre Viva 123",
        city="Temuco",
        org_phone="+56912345678",
        web="https://acme.example",
        supervisor_name="Ana Perez",
        supervisor_profession="Ingeniera Civil Informatica",
        supervisor_position="Jefa de Proyectos",
        supervisor_department="Tecnologia",
        supervisor_email="ana.perez@acme.example",
        supervisor_phone="+56987654321",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 8, 31),
        schedule="09:00-18:00",
        days="Lunes a viernes",
        modality="Presencial",
        internship_address="Av. Practica 456",
        act_description="Desarrollo de funcionalidades backend.",
        ben_description="Apoyo al equipo de plataforma.",
        amount=120000,
        internship_period=PracticePeriodEnum.semester,
        internship_type=PracticeTypeEnum.controlled_practice,
    )


class InMemoryNotificationRepository:
    def __init__(self) -> None:
        self.notifications = []

    async def create(self, notification):
        notification.id = len(self.notifications) + 1
        self.notifications.append(notification)
        return notification

    async def update_status(self, notification_id, new_status, sent_at=None):
        notification = self.notifications[notification_id - 1]
        notification.status = new_status
        notification.sent_at = sent_at
        return notification


class FakeInternshipRepository:
    def __init__(self) -> None:
        self.reviewer = _user(
            20,
            "director@example.com",
            "Director de carrera",
        )
        self.states = {
            "Pendiente": _state(1, "Pendiente"),
            "En revisión": _state(2, "En revisión"),
            "Aprobada": _state(3, "Aprobada"),
            "Rechazada": _state(4, "Rechazada"),
            "En revisión DIRAE": _state(5, "En revisión DIRAE"),
        }
        self.internship_by_id = None

    async def get_student_requirement(self, user_id: int, requirement: str):
        return SimpleNamespace(is_completed=True)

    async def get_blocking_internship_for_registration(self, **kwargs):
        return None

    async def get_state_by_title(self, title: str):
        return self.states.get(title)

    async def create_internship_with_history(
        self,
        internship,
        initial_status,
        actor_id,
        reason,
        metadata=None,
    ):
        created = SimpleNamespace(
            id=100,
            org_name=internship.org_name,
            user_id=internship.user_id,
            internship_period=internship.internship_period,
            internship_type=internship.internship_type,
            has_school_insurance=internship.has_school_insurance,
            status_id=initial_status.id,
            status=initial_status,
            student=_user(
                internship.user_id,
                "student@example.com",
                "Estudiante",
            ),
        )
        self.internship_by_id = created
        return created

    async def list_users_by_roles(self, role_names: set[str]):
        return [self.reviewer]

    async def get_internship_by_id(self, internship_id: int):
        return self.internship_by_id

    async def update_internship_status_with_history(
        self,
        internship,
        previous_status,
        new_status,
        actor_id,
        reason,
        metadata=None,
    ):
        internship.status = new_status
        internship.status_id = new_status.id
        return internship

    async def get_exception_by_rule(self, internship_id: int, rule: str):
        if rule == "parallel_course":
            return SimpleNamespace(id=1, rule="parallel_course")
        return None

    async def upsert_academic_requirement_status(
        self,
        user_id: int,
        practice_type: str,
        new_status: str,
        updated_by: int,
    ):
        return SimpleNamespace(status=new_status)


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.reviewer = _user(
            20,
            "director@example.com",
            "Director de carrera",
        )
        self.student = _user(10, "student@example.com", "Estudiante")
        self.internship = SimpleNamespace(
            id=100,
            org_name="Acme Chile",
            user_id=10,
            status=_state(1, "Pendiente"),
            student=self.student,
        )
        self.document_type = SimpleNamespace(
            id=1,
            name="Formulario de inscripción",
            is_active=True,
        )
        self.documents_by_id = {}

    async def get_internship_by_id(self, internship_id: int):
        return self.internship

    async def get_document_type_by_id(self, document_type_id: int):
        return self.document_type

    async def create_document(self, document):
        created = SimpleNamespace(
            id=55,
            file_name=document.file_name,
            file_path=document.file_path,
            extension=document.extension,
            status=document.status,
            size_bytes=document.size_bytes,
            internship_id=document.internship_id,
            type_id=document.type_id,
            user_id=document.user_id,
            reviewed_at=None,
            reviewed_by=None,
            review_comment=None,
            deleted_at=None,
            deleted_by=None,
            internship=self.internship,
            document_type=self.document_type,
        )
        self.documents_by_id[created.id] = created
        return created

    async def get_document_by_id(self, document_id: int):
        return self.documents_by_id.get(document_id)

    async def update_document_status(
        self,
        document,
        new_status,
        reviewer_id,
        comment,
    ):
        document.status = new_status
        document.reviewed_by = reviewer_id
        document.review_comment = comment
        document.reviewed_at = datetime(2026, 6, 1, 10, 0, 0)
        return document

    async def list_users_by_roles(self, role_names: set[str]):
        return [self.reviewer]


def _notification_service(repository) -> NotificationService:
    return NotificationService(
        notification_repository=repository,
        app_config=_notification_config(),
    )


@pytest.mark.asyncio
async def test_internship_lifecycle_events_are_persisted_in_simulated_mode():
    notification_repository = InMemoryNotificationRepository()
    internship_repository = FakeInternshipRepository()
    service = InternshipService(
        internship_repository=internship_repository,
        notification_service=_notification_service(notification_repository),
    )

    created = await service.create_internship(
        internship_data=_internship_payload(),
        user_id=10,
    )
    director = _user(20, "director@example.com", "Director de carrera")
    secretaria = _user(30, "secretaria@example.com", "Secretaria de Carrera")

    await service.approve(created.id, director, comment="Cumple requisitos")
    created.status = internship_repository.states["Pendiente"]
    await service.reject(created.id, director, comment="No cumple requisitos")
    created.status = internship_repository.states["Pendiente"]
    await service.derive(created.id, secretaria, comment="Revisión DIRAE")

    notifications = notification_repository.notifications

    assert [notification.status for notification in notifications] == [
        NotificationStatusEnum.simulated,
        NotificationStatusEnum.simulated,
        NotificationStatusEnum.simulated,
        NotificationStatusEnum.simulated,
    ]
    assert notifications[0].event_type == NotificationEventTypeEnum.custom
    assert notifications[0].payload == {
        "event": "internship_created",
        "internship_id": created.id,
        "student_user_id": created.user_id,
    }
    assert notifications[1].event_type == NotificationEventTypeEnum.internship_approved
    assert notifications[1].payload == {"internship_id": created.id}
    assert notifications[2].event_type == NotificationEventTypeEnum.internship_rejected
    assert notifications[2].payload["reason"] == "No cumple requisitos"
    assert notifications[3].event_type == NotificationEventTypeEnum.internship_derived
    assert notifications[3].payload["reason"] == "Revisión DIRAE"


@pytest.mark.asyncio
async def test_document_events_are_persisted_in_simulated_mode(tmp_path):
    notification_repository = InMemoryNotificationRepository()
    document_repository = FakeDocumentRepository()
    service = DocumentService(
        document_repository=document_repository,
        app_config=_document_config(tmp_path),
        notification_service=_notification_service(notification_repository),
    )

    student = _user(10, "student@example.com", "Estudiante")
    reviewer = _user(20, "director@example.com", "Director de carrera")
    document = await service.upload_document(
        internship_id=100,
        document_type_id=1,
        file_name="formulario.pdf",
        content=b"pdf-data",
        actor=student,
    )
    await service.update_document_status(
        document_id=document.id,
        new_status=DocumentStatusEnum.observed,
        comment="Falta firma",
        actor=reviewer,
    )
    await service.update_document_status(
        document_id=document.id,
        new_status=DocumentStatusEnum.approved,
        comment=None,
        actor=reviewer,
    )

    notifications = notification_repository.notifications

    assert [notification.status for notification in notifications] == [
        NotificationStatusEnum.simulated,
        NotificationStatusEnum.simulated,
        NotificationStatusEnum.simulated,
    ]
    assert notifications[0].event_type == NotificationEventTypeEnum.custom
    assert notifications[0].payload == {
        "event": "document_uploaded",
        "document_id": document.id,
        "internship_id": document.internship_id,
        "document_type": "Formulario de inscripción",
    }
    assert notifications[1].payload["event"] == "document_status_changed"
    assert notifications[1].payload["new_status"] == "observed"
    assert notifications[1].payload["comment"] == "Falta firma"
    assert notifications[2].payload["event"] == "document_status_changed"
    assert notifications[2].payload["new_status"] == "approved"
    assert notifications[2].payload["comment"] is None
