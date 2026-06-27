from fastapi.testclient import TestClient

from app.modules.auth.utils.roles import SECRETARY_ROLE, STUDENT_ROLE


def test_student_uploads_document_and_document_role_approves_it(
    client: TestClient,
    create_user,
    mark_induction_completed,
    create_document_type,
    auth_headers,
    internship_payload,
) -> None:
    student_id = create_user(
        email="estudiante.document.e2e@example.com",
        rut="66666666-6",
        roles=[STUDENT_ROLE],
    )
    create_user(
        email="secretaria.document.e2e@example.com",
        rut="77777777-7",
        roles=[SECRETARY_ROLE],
    )
    mark_induction_completed(student_id)
    document_type_id = create_document_type()

    created = client.post(
        "/internships",
        headers=auth_headers("estudiante.document.e2e@example.com"),
        json=internship_payload(),
    )
    assert created.status_code == 201, created.text
    internship_id = created.json()["id"]

    upload = client.post(
        f"/internships/{internship_id}/documents",
        headers=auth_headers("estudiante.document.e2e@example.com"),
        data={"document_type_id": str(document_type_id)},
        files={"file": ("formulario.pdf", b"contenido pdf", "application/pdf")},
    )

    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]
    assert upload.json()["status"] == "uploaded"

    download = client.get(
        f"/documents/{document_id}/download",
        headers=auth_headers("secretaria.document.e2e@example.com"),
    )

    assert download.status_code == 200, download.text
    assert download.content == b"contenido pdf"

    reviewed = client.patch(
        f"/documents/{document_id}/status",
        headers=auth_headers("secretaria.document.e2e@example.com"),
        json={"status": "approved", "comment": "Documento correcto"},
    )

    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "approved"
    assert reviewed.json()["reviewed_by"] is not None
    assert reviewed.json()["review_comment"] == "Documento correcto"
