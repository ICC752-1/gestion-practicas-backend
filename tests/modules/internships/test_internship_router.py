from app.main import app


def test_internships_router_is_registered() -> None:
    paths = {route.path for route in app.routes}

    assert "/internships" in paths
    assert "/internships/me" in paths
    assert "/internships/{internship_id}" in paths


def test_users_and_roles_routers_are_registered() -> None:
    paths = {route.path for route in app.routes}

    assert "/users" in paths
    assert "/users/{user_id}" in paths
    assert "/users/{user_id}/roles" in paths
    assert "/users/{user_id}/roles/{role_id}" in paths
    assert "/roles" in paths
    assert "/roles/{role_id}" in paths
