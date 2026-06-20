"""Tests de contrato para modelos de notificaciones."""

from app.modules.notifications.models.notification_model import (
    Notification,
    NotificationEventTypeEnum,
    NotificationStatusEnum,
)


def test_notification_model_matches_database_contract() -> None:
    columns = Notification.__table__.c

    assert Notification.__tablename__ == "notification"
    assert "recipient_user_id" in columns
    assert "recipient_email" in columns
    assert "event_type" in columns
    assert "subject" in columns
    assert "content" in columns
    assert "status" in columns
    assert "payload" in columns
    assert "created_at" in columns
    assert "sent_at" in columns


def test_notification_event_type_enum_matches_business_contract() -> None:
    values = {event_type.value for event_type in NotificationEventTypeEnum}

    assert values == {
        "internship_approved",
        "internship_rejected",
        "internship_derived",
        "requirement_status_changed",
        "custom",
    }


def test_notification_status_enum_matches_delivery_contract() -> None:
    values = {status.value for status in NotificationStatusEnum}

    assert values == {"simulated", "pending", "sent", "failed"}
