from fastapi.testclient import TestClient

from app.modules.auth.utils.roles import CAREER_DIRECTOR_ROLE, STUDENT_ROLE


def test_student_creates_internship_and_admin_approves(
    client: TestClient,
    create_user,
    mark_induction_completed,
    auth_headers,
    internship_payload,
    internship_status_title,
) -> None:
    student_id = create_user(
        email="estudiante.internship.e2e@example.com",
        rut="22222222-2",
        roles=[STUDENT_ROLE],
    )
    create_user(
        email="director.internship.e2e@example.com",
        rut="33333333-3",
        roles=[CAREER_DIRECTOR_ROLE],
    )
    mark_induction_completed(student_id)

    created = client.post(
        "/internships",
        headers=auth_headers("estudiante.internship.e2e@example.com"),
        json=internship_payload(),
    )

    assert created.status_code == 201, created.text
    internship_id = created.json()["id"]
    assert internship_status_title(internship_id) == "Pendiente"

    approved = client.post(
        f"/internships/{internship_id}/approve",
        headers=auth_headers("director.internship.e2e@example.com"),
        json={"comment": "Aprobación E2E"},
    )

    assert approved.status_code == 200, approved.text
    assert internship_status_title(internship_id) == "Aprobada"

    tracking = client.get(
        f"/internships/{internship_id}/tracking",
        headers=auth_headers("estudiante.internship.e2e@example.com"),
    )

    assert tracking.status_code == 200, tracking.text
    assert [item["new_status"]["title"] for item in tracking.json()] == [
        "Pendiente",
        "Aprobada",
    ]

    requirements = client.get(
        f"/admin/students/{student_id}/internship-requirements",
        headers=auth_headers("director.internship.e2e@example.com"),
    )

    assert requirements.status_code == 200, requirements.text
    assert any(
        item["type"] == "Práctica de Estudio I" and item["status"] == "Aprobada"
        for item in requirements.json()
    )


def test_out_of_period_internship_is_blocked_until_director_validates_insurance(
    client: TestClient,
    create_user,
    mark_induction_completed,
    auth_headers,
    internship_payload,
    internship_status_title,
) -> None:
    student_id = create_user(
        email="estudiante.insurance.e2e@example.com",
        rut="44444444-4",
        roles=[STUDENT_ROLE],
    )
    create_user(
        email="director.insurance.e2e@example.com",
        rut="55555555-5",
        roles=[CAREER_DIRECTOR_ROLE],
    )
    mark_induction_completed(student_id)

    created = client.post(
        "/internships",
        headers=auth_headers("estudiante.insurance.e2e@example.com"),
        json=internship_payload(
            start_date="2026-07-01",
            end_date="2026-07-31",
            org_name="Empresa Fuera Periodo SpA",
        ),
    )

    assert created.status_code == 201, created.text
    internship_id = created.json()["id"]
    assert created.json()["insurance_status"] == "pending"

    blocked = client.post(
        f"/internships/{internship_id}/approve",
        headers=auth_headers("director.insurance.e2e@example.com"),
        json={"comment": "Intento sin seguro validado"},
    )

    assert blocked.status_code == 409, blocked.text
    assert internship_status_title(internship_id) == "Pendiente"

    validated = client.patch(
        f"/admin/internships/{internship_id}/school-insurance",
        headers=auth_headers("director.insurance.e2e@example.com"),
        json={"status": "validated", "notes": "Seguro validado en E2E"},
    )

    assert validated.status_code == 200, validated.text
    assert validated.json()["insurance_status"] == "validated"

    approved = client.post(
        f"/internships/{internship_id}/approve",
        headers=auth_headers("director.insurance.e2e@example.com"),
        json={"comment": "Aprobación posterior a seguro"},
    )

    assert approved.status_code == 200, approved.text
    assert internship_status_title(internship_id) == "Aprobada"
