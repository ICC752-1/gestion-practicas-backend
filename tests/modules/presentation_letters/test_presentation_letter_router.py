from app.main import app


def _methods_for_path(path: str) -> set[str]:
    methods: set[str] = set()

    for route in app.routes:
        if route.path == path and hasattr(route, "methods"):
            methods.update(route.methods)

    return methods


def test_presentation_letter_router_exposes_automatic_flow() -> None:
    paths = {route.path for route in app.routes}

    assert "/presentation-letters/templates" in paths
    assert "GET" in _methods_for_path("/presentation-letters/templates")
    assert "/presentation-letters/templates/{practice_type}" in paths
    assert "GET" in _methods_for_path("/presentation-letters/templates/{practice_type}")
    assert "PUT" in _methods_for_path("/presentation-letters/templates/{practice_type}")
    assert "/presentation-letters/generate" in paths
    assert "POST" in _methods_for_path("/presentation-letters/generate")
    assert "/presentation-letters/me" in paths
    assert "GET" in _methods_for_path("/presentation-letters/me")
    assert "/presentation-letters/{letter_id}/download" in paths
    assert "GET" in _methods_for_path("/presentation-letters/{letter_id}/download")


def test_presentation_letter_router_does_not_expose_manual_status_flow() -> None:
    paths = {route.path for route in app.routes}

    assert "/presentation-letters/{request_id}/cancel" not in paths
    assert "/presentation-letters/{request_id}/start" not in paths
    assert "/presentation-letters/{request_id}/issue" not in paths
    assert "/presentation-letters/{request_id}/reject" not in paths
