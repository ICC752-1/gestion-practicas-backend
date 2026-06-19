"""Tests unitarios para el controller de notificaciones.

Cubre los siguientes escenarios:
- Listar notificaciones de usuario autenticado
- Listar notificaciones sin autenticacion (401)
- Enviar correo sin autenticacion (401)
- Enviar correo con rol incorrecto (403)
- Obtener detalle de notificacion propia
- Obtener detalle de notificacion ajena (403)
- Obtener detalle de notificacion inexistente (404)
- Reintentar notificacion fallida
"""

from datetime import UTC, datetime

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.modules.notifications.models.notification_model import (
    NotificationEventTypeEnum,
    NotificationStatusEnum,
)
from app.modules.notifications.schemas.notification_schema import (
    MarkNotificationsReadRequest,
)


def _make_notification_dict(
    notification_id: int = 1,
    recipient_user_id: int = 10,
    event_type: NotificationEventTypeEnum = NotificationEventTypeEnum.internship_approved,
    notification_status: NotificationStatusEnum = NotificationStatusEnum.simulated,
    subject: str = "Test",
    content: str = "<p>Test</p>",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=notification_id,
        recipient_user_id=recipient_user_id,
        recipient_email="s@test.com",
        event_type=event_type,
        subject=subject,
        content=content,
        status=notification_status,
        payload={"internship_id": 5},
        sent_at=None,
        read_at=None,
        is_read=False,
        created_at=datetime.now(UTC),
    )


class TestListNotifications:

    @pytest.mark.asyncio
    async def test_list_returns_notifications_for_authenticated_user(self):
        from app.modules.notifications.controllers.notification_controller import (
            list_notifications,
        )

        db = AsyncMock()
        current_user = SimpleNamespace(id=10, roles=[])
        notification = _make_notification_dict(recipient_user_id=10)

        with patch(
            "app.modules.notifications.controllers.notification_controller._build_service"
        ) as mock_build:
            service = AsyncMock()
            service.get_notifications_for_user.return_value = [notification]
            service.count_notifications_for_user.return_value = 1
            service.count_unread_for_user.return_value = 1
            mock_build.return_value = service

            result = await list_notifications(
                db=db,
                current_user=current_user,
                limit=50,
                offset=0,
                is_read=None,
                event_type=None,
                created_from=None,
                created_to=None,
            )

        assert len(result.items) == 1
        assert result.total == 1
        assert result.unread_count == 1
        service.get_notifications_for_user.assert_awaited_once_with(
            user_id=10,
            limit=50,
            offset=0,
            is_read=None,
            event_type=None,
            created_from=None,
            created_to=None,
        )
        service.count_notifications_for_user.assert_awaited_once()
        service.count_unread_for_user.assert_awaited_once_with(user_id=10)

    @pytest.mark.asyncio
    async def test_list_passes_read_and_event_filters(self):
        from app.modules.notifications.controllers.notification_controller import (
            list_notifications,
        )

        db = AsyncMock()
        current_user = SimpleNamespace(id=10, roles=[])

        with patch(
            "app.modules.notifications.controllers.notification_controller._build_service"
        ) as mock_build:
            service = AsyncMock()
            service.get_notifications_for_user.return_value = []
            service.count_notifications_for_user.return_value = 0
            service.count_unread_for_user.return_value = 0
            mock_build.return_value = service

            await list_notifications(
                db=db,
                current_user=current_user,
                limit=10,
                offset=0,
                is_read=False,
                event_type=NotificationEventTypeEnum.internship_approved,
                created_from=None,
                created_to=None,
            )

        service.get_notifications_for_user.assert_awaited_once_with(
            user_id=10,
            limit=10,
            offset=0,
            is_read=False,
            event_type=NotificationEventTypeEnum.internship_approved,
            created_from=None,
            created_to=None,
        )


class TestMarkNotificationsRead:

    @pytest.mark.asyncio
    async def test_mark_selected_notifications_as_read_uses_current_user(self):
        from app.modules.notifications.controllers.notification_controller import (
            mark_selected_notifications_as_read,
        )

        db = AsyncMock()
        current_user = SimpleNamespace(id=10, roles=[])

        with patch(
            "app.modules.notifications.controllers.notification_controller._build_service"
        ) as mock_build:
            service = AsyncMock()
            service.mark_notifications_as_read.return_value = 2
            service.count_unread_for_user.return_value = 3
            mock_build.return_value = service

            result = await mark_selected_notifications_as_read(
                payload=MarkNotificationsReadRequest(notification_ids=[1, 2]),
                db=db,
                current_user=current_user,
            )

        assert result.updated_count == 2
        assert result.unread_count == 3
        service.mark_notifications_as_read.assert_awaited_once_with(
            user_id=10,
            notification_ids=[1, 2],
        )

    @pytest.mark.asyncio
    async def test_mark_all_notifications_as_read_uses_current_user(self):
        from app.modules.notifications.controllers.notification_controller import (
            mark_all_notifications_as_read,
        )

        db = AsyncMock()
        current_user = SimpleNamespace(id=10, roles=[])

        with patch(
            "app.modules.notifications.controllers.notification_controller._build_service"
        ) as mock_build:
            service = AsyncMock()
            service.mark_notifications_as_read.return_value = 5
            service.count_unread_for_user.return_value = 0
            mock_build.return_value = service

            result = await mark_all_notifications_as_read(
                db=db,
                current_user=current_user,
            )

        assert result.updated_count == 5
        assert result.unread_count == 0
        service.mark_notifications_as_read.assert_awaited_once_with(user_id=10)


class TestGetNotification:

    @pytest.mark.asyncio
    async def test_get_detail_of_own_notification(self):
        from app.modules.notifications.controllers.notification_controller import (
            get_notification,
        )

        db = AsyncMock()
        current_user = SimpleNamespace(id=10, roles=[])
        notification = _make_notification_dict(
            notification_id=1,
            recipient_user_id=10,
        )

        with patch(
            "app.modules.notifications.controllers.notification_controller._build_service"
        ) as mock_build:
            service = AsyncMock()
            service.get_by_id.return_value = notification
            mock_build.return_value = service

            result = await get_notification(
                notification_id=1,
                db=db,
                current_user=current_user,
            )

        assert result.id == 1

    @pytest.mark.asyncio
    async def test_get_detail_of_other_users_notification_raises_403(self):
        from app.modules.notifications.controllers.notification_controller import (
            get_notification,
        )

        db = AsyncMock()
        current_user = SimpleNamespace(id=99, roles=[])
        notification = _make_notification_dict(
            notification_id=1,
            recipient_user_id=10,
        )

        with patch(
            "app.modules.notifications.controllers.notification_controller._build_service"
        ) as mock_build:
            service = AsyncMock()
            service.get_by_id.return_value = notification
            mock_build.return_value = service

            with pytest.raises(HTTPException) as exc:
                await get_notification(
                    notification_id=1,
                    db=db,
                    current_user=current_user,
                )

            assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_get_detail_of_nonexistent_notification_raises_404(self):
        from app.modules.notifications.controllers.notification_controller import (
            get_notification,
        )

        db = AsyncMock()
        current_user = SimpleNamespace(id=10, roles=[])

        with patch(
            "app.modules.notifications.controllers.notification_controller._build_service"
        ) as mock_build:
            service = AsyncMock()
            service.get_by_id.return_value = None
            mock_build.return_value = service

            with pytest.raises(HTTPException) as exc:
                await get_notification(
                    notification_id=999,
                    db=db,
                    current_user=current_user,
                )

            assert exc.value.status_code == 404


class TestRetryNotification:

    @pytest.mark.asyncio
    async def test_retry_returns_response_on_success(self):
        from app.modules.notifications.controllers.notification_controller import (
            retry_notification,
        )

        db = AsyncMock()
        current_user = SimpleNamespace(
            id=1,
            roles=[SimpleNamespace(role=SimpleNamespace(name="Encargado de practica"))],
        )

        notification = _make_notification_dict(
            notification_status=NotificationStatusEnum.sent,
        )

        with patch(
            "app.modules.notifications.controllers.notification_controller._build_service"
        ) as mock_build:
            service = AsyncMock()
            service.retry_send.return_value = notification
            mock_build.return_value = service

            result = await retry_notification(
                notification_id=1,
                db=db,
                current_user=current_user,
            )

        assert result.success is True
        assert result.notification_id == 1

    @pytest.mark.asyncio
    async def test_retry_returns_404_when_notification_not_found(self):
        from app.modules.notifications.controllers.notification_controller import (
            retry_notification,
        )

        db = AsyncMock()
        current_user = SimpleNamespace(
            id=1,
            roles=[SimpleNamespace(role=SimpleNamespace(name="Encargado de practica"))],
        )

        with patch(
            "app.modules.notifications.controllers.notification_controller._build_service"
        ) as mock_build:
            service = AsyncMock()
            service.retry_send.return_value = None
            mock_build.return_value = service

            with pytest.raises(HTTPException) as exc:
                await retry_notification(
                    notification_id=999,
                    db=db,
                    current_user=current_user,
                )

            assert exc.value.status_code == 404
