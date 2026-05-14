from app.main import app


def test_internships_router_is_registered() -> None:
    paths = {route.path for route in app.routes}

    assert "/internships" in paths
    assert "/internships/me" in paths
    assert "/internships/{internship_id}" in paths
