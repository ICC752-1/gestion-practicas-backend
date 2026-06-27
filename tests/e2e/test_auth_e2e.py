from fastapi.testclient import TestClient

from app.modules.auth.utils.roles import STUDENT_ROLE


def test_login_me_refresh_and_logout_flow(client: TestClient, create_user) -> None:
    create_user(
        email="estudiante.auth.e2e@example.com",
        rut="11111111-1",
        roles=[STUDENT_ROLE],
        first_name="Ana",
        last_name="Auth",
    )

    login = client.post(
        "/auth/login",
        json={"email": "estudiante.auth.e2e@example.com", "password": "Secret123!"},
    )

    assert login.status_code == 200, login.text
    tokens = login.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me = client.get("/auth/me", headers=headers)

    assert me.status_code == 200, me.text
    assert me.json()["email"] == "estudiante.auth.e2e@example.com"
    assert me.json()["roles"] == [STUDENT_ROLE]

    refresh = client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert refresh.status_code == 200, refresh.text
    rotated_tokens = refresh.json()
    assert rotated_tokens["access_token"]
    assert rotated_tokens["refresh_token"] != tokens["refresh_token"]

    reused_refresh = client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert reused_refresh.status_code == 401

    logout = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {rotated_tokens['access_token']}"},
        json={"refresh_token": rotated_tokens["refresh_token"]},
    )

    assert logout.status_code == 204, logout.text

    refresh_after_logout = client.post(
        "/auth/refresh",
        json={"refresh_token": rotated_tokens["refresh_token"]},
    )

    assert refresh_after_logout.status_code == 401
