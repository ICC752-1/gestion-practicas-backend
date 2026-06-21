from datetime import UTC, datetime
from types import SimpleNamespace

from app.modules.auth.controllers.user_controller import (
    _dispatch_account_activation_notification,
)
from app.modules.notifications.models.notification_model import (
    NotificationEventTypeEnum,
    NotificationStatusEnum,
)


class FakeNotificationService:
    def __init__(self) -> None:
        self.notifications = []

    async def create_and_dispatch(self, notification):
        self.notifications.append(notification)
        return notification


class FailingNotificationService:
    async def create_and_dispatch(self, notification):
        raise RuntimeError("smtp unavailable")


async def test_dispatch_account_activation_notification_builds_email() -> None:
    service = FakeNotificationService()
    user = SimpleNamespace(id=7, email="nuevo.usuario@ufromail.cl")
    expires_at = datetime(2026, 6, 21, 12, 30, tzinfo=UTC).replace(tzinfo=None)

    await _dispatch_account_activation_notification(
        notification_service=service,
        user=user,
        activation_url="http://localhost:5173/activar-cuenta?token=raw-token",
        expires_at=expires_at,
    )

    assert len(service.notifications) == 1
    notification = service.notifications[0]
    assert notification.recipient_user_id == 7
    assert notification.recipient_email == "nuevo.usuario@ufromail.cl"
    assert notification.event_type == NotificationEventTypeEnum.custom
    assert notification.status == NotificationStatusEnum.simulated
    assert notification.subject == "Cuenta creada en Sistema de Gestión de Prácticas"
    assert "http://localhost:5173/activar-cuenta?token=raw-token" in notification.content
    assert "Activar cuenta" in notification.content
    assert "nuevo.usuario@ufromail.cl" in notification.content
    assert "Credencial temporal" not in notification.content
    assert notification.payload == {
        "event": "user_account_activation_created",
        "recipient_user_id": 7,
        "expires_at": "2026-06-21T12:30:00",
    }


async def test_dispatch_account_activation_notification_is_non_blocking() -> None:
    user = SimpleNamespace(id=7, email="nuevo.usuario@ufromail.cl")

    await _dispatch_account_activation_notification(
        notification_service=FailingNotificationService(),
        user=user,
        activation_url="http://localhost:5173/activar-cuenta?token=raw-token",
        expires_at=datetime(2026, 6, 21, 12, 30),
    )
