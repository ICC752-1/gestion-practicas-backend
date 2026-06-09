from app.main import app


def _methods_for_path(path: str) -> set[str]:
    methods: set[str] = set()

    for route in app.routes:
        if route.path == path and hasattr(route, "methods"):
            methods.update(route.methods)

    return methods


def test_google_oauth_routes_are_registered() -> None:
    paths = {route.path for route in app.routes}

    assert "/auth/google/login" in paths
    assert "GET" in _methods_for_path("/auth/google/login")
    assert "/auth/google/callback" in paths
    assert "GET" in _methods_for_path("/auth/google/callback")
