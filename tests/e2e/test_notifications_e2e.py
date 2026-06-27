from fastapi.testclient import TestClient

from app.modules.auth.utils.roles import CAREER_DIRECTOR_ROLE, STUDENT_ROLE


def test_real_internship_action_generates_notification_visible_to_student(
    client: TestClient,
    create_user,
    mark_induction_completed,
    auth_headers,
    internship_payload,
) -> None:
    student_id = create_user(
        email="estudiante.notification.e2e@example.com",
        rut="99999999-9",
        roles=[STUDENT_ROLE],
    )
    create_user(
        email="director.notification.e2e@example.com",
        rut="10101010-1",
        roles=[CAREER_DIRECTOR_ROLE],
    )
    mark_induction_completed(student_id)

    created = client.post(
        "/internships",
        headers=auth_headers("estudiante.notification.e2e@example.com"),
        json=internship_payload(org_name="Empresa Notificaciones SpA"),
    )
    assert created.status_code == 201, created.text
    internship_id = created.json()["id"]

    approved = client.post(
        f"/internships/{internship_id}/approve",
        headers=auth_headers("director.notification.e2e@example.com"),
        json={"comment": "Aprobación que genera notificación"},
    )
    assert approved.status_code == 200, approved.text

    notifications = client.get(
        "/notifications",
        headers=auth_headers("estudiante.notification.e2e@example.com"),
    )

    assert notifications.status_code == 200, notifications.text
    body = notifications.json()
    assert body["total"] >= 1
    notification = next(
        item
        for item in body["items"]
        if item["event_type"] == "internship_approved"
    )
    assert notification["subject"] == "Solicitud de práctica aprobada"
    assert notification["status"] == "simulated"
    assert notification["is_read"] is False

    detail = client.get(
        f"/notifications/{notification['id']}",
        headers=auth_headers("estudiante.notification.e2e@example.com"),
    )

    assert detail.status_code == 200, detail.text
    assert detail.json()["recipient_user_id"] == student_id
    assert detail.json()["payload"] == {"internship_id": internship_id}

    other_student_id = create_user(
        email="otro.estudiante.notification.e2e@example.com",
        rut="12121212-2",
        roles=[STUDENT_ROLE],
    )
    mark_induction_completed(other_student_id)

    forbidden = client.get(
        f"/notifications/{notification['id']}",
        headers=auth_headers("otro.estudiante.notification.e2e@example.com"),
    )

    assert forbidden.status_code == 403
