from app.main import app


def _methods_for_path(path: str) -> set[str]:
    methods: set[str] = set()

    for route in app.routes:
        if route.path == path and hasattr(route, "methods"):
            methods.update(route.methods)

    return methods


def test_auth_router_exposes_oauth2_session_endpoints() -> None:
    paths = {route.path for route in app.routes}

    assert "/auth/login" in paths
    assert "POST" in _methods_for_path("/auth/login")
    assert "/auth/complete-temporary-password" in paths
    assert "POST" in _methods_for_path("/auth/complete-temporary-password")
    assert "/auth/activate-account" in paths
    assert "POST" in _methods_for_path("/auth/activate-account")
    assert "/auth/activation-info" in paths
    assert "GET" in _methods_for_path("/auth/activation-info")
    assert "/auth/refresh" in paths
    assert "POST" in _methods_for_path("/auth/refresh")
    assert "/auth/me" in paths
    assert "/auth/logout" in paths


def test_google_oauth_routes_are_registered() -> None:
    paths = {route.path for route in app.routes}

    assert "/auth/google/login" in paths
    assert "GET" in _methods_for_path("/auth/google/login")
    assert "/auth/google/callback" in paths
    assert "GET" in _methods_for_path("/auth/google/callback")
