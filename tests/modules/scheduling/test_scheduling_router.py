from app.main import app


def _methods_for_path(path: str) -> set[str]:
    methods: set[str] = set()

    for route in app.routes:
        if route.path == path and hasattr(route, "methods"):
            methods.update(route.methods)

    return methods


def test_scheduling_router_is_registered() -> None:
    paths = {route.path for route in app.routes}

    assert "/scheduling/availability" in paths
    assert "POST" in _methods_for_path("/scheduling/availability")
    assert "/scheduling/availability/{slot_id}" in paths
    assert "PUT" in _methods_for_path("/scheduling/availability/{slot_id}")
    assert "DELETE" in _methods_for_path("/scheduling/availability/{slot_id}")
    assert "/scheduling/slots" in paths
    assert "GET" in _methods_for_path("/scheduling/slots")
    assert "/scheduling/appointments" in paths
    assert "GET" in _methods_for_path("/scheduling/appointments")
    assert "/scheduling/slots/{slot_id}/reserve" in paths
    assert "POST" in _methods_for_path("/scheduling/slots/{slot_id}/reserve")
    assert "/scheduling/appointments/{appointment_id}/cancel" in paths
    assert "POST" in _methods_for_path(
        "/scheduling/appointments/{appointment_id}/cancel"
    )
    assert "/scheduling/appointments/{appointment_id}/reschedule" in paths
    assert "POST" in _methods_for_path(
        "/scheduling/appointments/{appointment_id}/reschedule"
    )
    assert "/scheduling/appointments/{appointment_id}/outcome" in paths
    assert "PATCH" in _methods_for_path(
        "/scheduling/appointments/{appointment_id}/outcome"
    )
    assert "/scheduling/availability/{slot_id}/close" in paths
    assert "POST" in _methods_for_path("/scheduling/availability/{slot_id}/close")
