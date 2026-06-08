"""Tests unitarios para el servicio de notificaciones.

Cubre los siguientes escenarios:
- Creacion de notificacion en modo simulated
- Creacion de notificacion en modo real con envio SMTP exitoso
- Creacion de notificacion en modo real con fallo SMTP
- Destinatario invalido (sin user_id ni email)
- Payload almacenado como JSONB
- Helpers de eventos: aprobacion, rechazo, derivacion, cambio de requisito
- Despacho de notificacion desde servicio externo
"""

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.modules.notifications.models.notification_model import (
    NotificationEventTypeEnum,
    NotificationStatusEnum,
)
from app.modules.notifications.services.notification_service import (
    NotificationService,
)
from app.modules.notifications.utils.notification_event_helpers import (
    build_internship_approved_notification,
    build_internship_derived_notification,
    build_internship_rejected_notification,
    build_requirement_status_changed_notification,
)


def _make_config(mode: str = "simulated") -> SimpleNamespace:
    return SimpleNamespace(
        NOTIFICATION_MODE=mode,
        MAIL_USERNAME="test@example.com",
        MAIL_PASSWORD="password",
        MAIL_FROM="test@example.com",
        MAIL_PORT=587,
        MAIL_SERVER="smtp.gmail.com",
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
    )


def _make_real_config() -> SimpleNamespace:
    return SimpleNamespace(
        NOTIFICATION_MODE="real",
        MAIL_USERNAME="real@gmail.com",
        MAIL_PASSWORD="real-app-password",
        MAIL_FROM="real@gmail.com",
        MAIL_PORT=587,
        MAIL_SERVER="smtp.gmail.com",
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
    )


def _make_notification(
    notification_id: int = 1,
    recipient_user_id: int = 10,
    recipient_email: str | None = "student@test.com",
    event_type: NotificationEventTypeEnum = NotificationEventTypeEnum.custom,
    status: NotificationStatusEnum = NotificationStatusEnum.simulated,
    subject: str = "Test",
    content: str = "<p>Test</p>",
    payload: dict | None = None,
) -> MagicMock:
    notification = MagicMock()
    notification.id = notification_id
    notification.recipient_user_id = recipient_user_id
    notification.recipient_email = recipient_email
    notification.event_type = event_type
    notification.status = status
    notification.subject = subject
    notification.content = content
    notification.payload = payload
    return notification


def _make_service(mode: str = "simulated") -> NotificationService:
    repo = AsyncMock()
    config = _make_config(mode) if mode == "simulated" else _make_real_config()
    return NotificationService(
        notification_repository=repo,
        app_config=config,
    )


class TestCreateSimulatedNotification:

    @pytest.mark.asyncio
    async def test_simulated_mode_persists_with_simulated_status(self):
        service = _make_service(mode="simulated")
        notification = _make_notification()
        service.repository.create.return_value = notification

        result = await service.create_and_dispatch(notification)

        assert result.status == NotificationStatusEnum.simulated
        service.repository.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_simulated_mode_does_not_invoke_smtp(self):
        service = _make_service(mode="simulated")
        notification = _make_notification()

        with patch.object(service, "_send_smtp") as mock_smtp:
            await service.create_and_dispatch(notification)
            mock_smtp.assert_not_called()


class TestCreateRealNotification:

    @pytest.mark.asyncio
    async def test_real_mode_persists_and_sends_smtp(self):
        service = _make_service(mode="real")
        notification = _make_notification()
        notification.id = 1
        notification.recipient_email = "student@test.com"
        notification.status = NotificationStatusEnum.pending

        service.repository.create.return_value = notification
        service.repository.update_status.return_value = notification
        service._mailer = AsyncMock()

        await service.create_and_dispatch(notification)

        service.repository.create.assert_awaited_once()
        service._mailer.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_real_mode_smtp_failure_marks_as_failed(self):
        service = _make_service(mode="real")
        notification = _make_notification()
        notification.id = 1
        notification.recipient_email = "student@test.com"
        notification.status = NotificationStatusEnum.pending

        service.repository.create.return_value = notification
        failed_notification = _make_notification(
            status=NotificationStatusEnum.failed,
        )
        service.repository.update_status.return_value = failed_notification
        service._mailer = AsyncMock()
        service._mailer.send_message.side_effect = Exception("SMTP error")

        await service.create_and_dispatch(notification)

        service.repository.update_status.assert_awaited()
        call_args = service.repository.update_status.call_args
        assert call_args.kwargs["new_status"] == NotificationStatusEnum.failed

    @pytest.mark.asyncio
    async def test_real_mode_falls_back_to_simulated_with_default_credentials(self):
        config = _make_config(mode="real")
        repo = AsyncMock()
        service = NotificationService(
            notification_repository=repo,
            app_config=config,
        )

        assert service._mailer is None
        assert service.mode == "real"

        notification = _make_notification()
        service.repository.create.return_value = notification

        result = await service.create_and_dispatch(notification)

        assert result.status == NotificationStatusEnum.simulated


class TestInvalidRecipient:

    @pytest.mark.asyncio
    async def test_send_email_raises_runtime_error_in_simulated_mode(self):
        from app.modules.notifications.schemas.notification_schema import (
            EmailNotificationRequest,
        )

        service = _make_service(mode="simulated")
        request = EmailNotificationRequest(
            to_emails=["test@test.com"],
            subject="Test",
            body="<p>Hello</p>",
        )

        with pytest.raises(RuntimeError, match="modo simulated"):
            await service.send_email(request)

    @pytest.mark.asyncio
    async def test_send_smtp_raises_on_no_recipient_email(self):
        service = _make_service(mode="real")
        service._mailer = AsyncMock()

        notification = _make_notification()
        notification.recipient_email = None

        with pytest.raises(ValueError, match="destinatario de correo"):
            await service._send_smtp(notification)


class TestPayloadStorage:

    def test_event_helpers_include_payload(self):
        notification = build_internship_approved_notification(
            recipient_user_id=10,
            recipient_email="s@test.com",
            internship_id=5,
            org_name="Acme Corp",
        )

        assert notification.payload == {"internship_id": 5}
        assert notification.event_type == NotificationEventTypeEnum.internship_approved

    def test_rejected_notification_includes_reason_in_payload(self):
        notification = build_internship_rejected_notification(
            recipient_user_id=10,
            recipient_email="s@test.com",
            internship_id=5,
            org_name="Acme Corp",
            reason="Documentacion incompleta",
        )

        assert notification.payload["reason"] == "Documentacion incompleta"
        assert notification.payload["internship_id"] == 5

    def test_requirement_notification_payload(self):
        notification = build_requirement_status_changed_notification(
            recipient_user_id=10,
            recipient_email="s@test.com",
            requirement_id=3,
            requirement_type="Práctica de Estudio I",
            new_status="Aprobada",
            previous_status="En revisión",
        )

        assert notification.payload["requirement_id"] == 3
        assert notification.payload["new_status"] == "Aprobada"
        assert notification.payload["previous_status"] == "En revisión"


class TestEventHelpers:

    def test_approved_notification_builds_correctly(self):
        notification = build_internship_approved_notification(
            recipient_user_id=10,
            recipient_email="s@test.com",
            internship_id=5,
            org_name="Acme Corp",
        )

        assert notification.event_type == NotificationEventTypeEnum.internship_approved
        assert notification.subject == "Práctica aprobada"
        assert "Acme Corp" in notification.content
        assert "aprobada" in notification.content
        assert notification.recipient_user_id == 10
        assert notification.recipient_email == "s@test.com"

    def test_rejected_notification_builds_correctly(self):
        notification = build_internship_rejected_notification(
            recipient_user_id=10,
            recipient_email=None,
            internship_id=5,
            org_name="Acme Corp",
            reason="Falta de documentos",
        )

        assert notification.event_type == NotificationEventTypeEnum.internship_rejected
        assert notification.subject == "Práctica rechazada"
        assert "rechazada" in notification.content
        assert "Falta de documentos" in notification.content
        assert notification.recipient_email is None

    def test_rejected_notification_without_reason(self):
        notification = build_internship_rejected_notification(
            recipient_user_id=10,
            recipient_email=None,
            internship_id=5,
            org_name="Acme Corp",
        )

        assert "Motivo" not in notification.content

    def test_derived_notification_builds_correctly(self):
        notification = build_internship_derived_notification(
            recipient_user_id=10,
            recipient_email="s@test.com",
            internship_id=5,
            org_name="Acme Corp",
            reason="Revision DIRAE",
        )

        assert notification.event_type == NotificationEventTypeEnum.internship_derived
        assert notification.subject == "Práctica derivada a DIRAE"
        assert "DIRAE" in notification.content
        assert "Revision DIRAE" in notification.content

    def test_requirement_status_changed_notification(self):
        notification = build_requirement_status_changed_notification(
            recipient_user_id=10,
            recipient_email="s@test.com",
            requirement_id=3,
            requirement_type="Práctica de Estudio I",
            new_status="Aprobada",
            previous_status="En revisión",
        )

        assert (
            notification.event_type
            == NotificationEventTypeEnum.requirement_status_changed
        )
        assert "Práctica de Estudio I" in notification.subject
        assert "Aprobada" in notification.content


class TestNotificationFromExternalService:

    @pytest.mark.asyncio
    async def test_internship_service_dispatches_notification_on_approve(self):
        from app.modules.internships.services.internship_service import (
            APPROVED_STATUS_TITLE,
            PENDING_STATUS_TITLE,
            InternshipService,
        )

        repo = AsyncMock()
        internship = MagicMock()
        internship.id = 1
        internship.user_id = 10
        internship.org_name = "Acme"
        internship.student = MagicMock()
        internship.student.email = "s@test.com"

        current_status = MagicMock()
        current_status.title = PENDING_STATUS_TITLE
        internship.status = current_status

        async def _update_with_history(
            internship, previous_status, new_status, actor_id, reason, metadata=None
        ):
            internship.status_id = new_status.id
            internship.status = new_status
            return internship

        repo.get_internship_by_id.return_value = internship
        repo.update_internship_status_with_history.side_effect = _update_with_history

        approved_state = MagicMock()
        approved_state.id = 3
        approved_state.title = APPROVED_STATUS_TITLE
        repo.get_state_by_title.return_value = approved_state

        notification_repo = AsyncMock()
        notification_repo.create.return_value = _make_notification()
        notification_service = NotificationService(
            notification_repository=notification_repo,
            app_config=_make_config("simulated"),
        )

        service = InternshipService(
            internship_repository=repo,
            notification_service=notification_service,
        )

        actor = MagicMock()
        actor.id = 99
        actor.roles = [
            SimpleNamespace(role=SimpleNamespace(name="Encargado de practica"))
        ]

        await service.approve(1, actor, comment=None)

        notification_repo.create.assert_awaited()

    @pytest.mark.asyncio
    async def test_internship_service_without_notification_service_skips_gracefully(self):
        from app.modules.internships.services.internship_service import (
            APPROVED_STATUS_TITLE,
            PENDING_STATUS_TITLE,
            InternshipService,
        )

        repo = AsyncMock()
        internship = MagicMock()
        internship.id = 1
        internship.user_id = 10
        internship.org_name = "Acme"
        internship.student = MagicMock()
        internship.student.email = "s@test.com"

        current_status = MagicMock()
        current_status.title = PENDING_STATUS_TITLE
        internship.status = current_status

        async def _update_with_history(
            internship, previous_status, new_status, actor_id, reason, metadata=None
        ):
            internship.status_id = new_status.id
            internship.status = new_status
            return internship

        repo.get_internship_by_id.return_value = internship
        repo.update_internship_status_with_history.side_effect = _update_with_history

        approved_state = MagicMock()
        approved_state.id = 3
        approved_state.title = APPROVED_STATUS_TITLE
        repo.get_state_by_title.return_value = approved_state

        service = InternshipService(
            internship_repository=repo,
            notification_service=None,
        )

        actor = MagicMock()
        actor.id = 99
        actor.roles = [
            SimpleNamespace(role=SimpleNamespace(name="Encargado de practica"))
        ]

        result = await service.approve(1, actor, comment=None)

        assert result is not None


class TestRetrySend:

    @pytest.mark.asyncio
    async def test_retry_returns_none_when_mailer_not_configured(self):
        service = _make_service(mode="simulated")
        result = await service.retry_send(notification_id=1)
        assert result is None

    @pytest.mark.asyncio
    async def test_retry_returns_none_for_nonexistent_notification(self):
        service = _make_service(mode="real")
        service._mailer = AsyncMock()
        service.repository.get_by_id.return_value = None

        result = await service.retry_send(notification_id=999)
        assert result is None

    @pytest.mark.asyncio
    async def test_retry_returns_none_for_already_sent_notification(self):
        service = _make_service(mode="real")
        service._mailer = AsyncMock()

        notification = _make_notification(
            status=NotificationStatusEnum.sent,
        )
        service.repository.get_by_id.return_value = notification

        result = await service.retry_send(notification_id=1)
        assert result is None

    @pytest.mark.asyncio
    async def test_retry_successful_for_failed_notification(self):
        service = _make_service(mode="real")
        service._mailer = AsyncMock()

        notification = _make_notification(
            status=NotificationStatusEnum.failed,
            recipient_email="s@test.com",
        )
        service.repository.get_by_id.return_value = notification
        service.repository.update_status.return_value = notification

        await service.retry_send(notification_id=1)

        service._mailer.send_message.assert_awaited_once()
        service.repository.update_status.assert_awaited()
