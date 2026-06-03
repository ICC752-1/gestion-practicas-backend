from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.modules.internships.services.internship_service import InternshipService

# Mapeo consistente para que los helpers y el repositorio falso usen las mismas IDs
STATE_IDS = {
    "Pendiente": 1,
    "En revisión": 2,
    "Aprobada": 3,
    "Rechazada": 4,
    "En revisión DIRAE": 5
}

def _status(title: str) -> SimpleNamespace:
    return SimpleNamespace(id=STATE_IDS.get(title, 99), title=title)

def _internship(status_title: str | None = None) -> SimpleNamespace:
    status_obj = _status(status_title) if status_title else None
    return SimpleNamespace(
        id=1,
        status=status_obj,
        status_id=status_obj.id if status_obj else None,
    )

def _user(roles: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        id=10,
        roles=[
            SimpleNamespace(role=SimpleNamespace(name=r))
            for r in roles
        ],
    )

class FakeInternshipRepository:
    def __init__(self, internship=None) -> None:
        self.internship = internship
        self.saved = None
        self._states = {
            title: SimpleNamespace(id=state_id, title=title)
            for title, state_id in STATE_IDS.items()
        }

    async def get_internship_by_id(self, internship_id: int):
        return self.internship

    async def get_state_by_title(self, title: str):
        if title not in self._states:
            raise HTTPException(500, f"Estado '{title}' no encontrado en BD")
        return self._states[title]

    async def save(self, internship):
        self.saved = internship
        return internship

    async def create_internship(self, internship): ...
    async def list_internships_by_user(self, user_id): return []
    async def list_dashboard_internships(self): return []


# =========================================================================
# TESTS (Soporte Asíncrono Habilitado)
# =========================================================================

@pytest.mark.anyio
async def test_coordinador_aprueba_stage_1() -> None:
    """Encargado de práctica aprueba: Pendiente → En revisión."""
    internship = _internship("Pendiente")
    repository = FakeInternshipRepository(internship=internship)
    service = InternshipService(internship_repository=repository)

    actor = _user(["Encargado de practica"])
    result = await service.approve(internship_id=1, actor=actor, comment=None)

    assert repository.saved is not None
    assert result.status_id == STATE_IDS["En revisión"]


@pytest.mark.anyio
async def test_director_aprueba_stage_2() -> None:
    """Director de carrera aprueba: En revisión → Aprobada."""
    internship = _internship("En revisión")
    repository = FakeInternshipRepository(internship=internship)
    service = InternshipService(internship_repository=repository)

    actor = _user(["Director de carrera"])
    result = await service.approve(internship_id=1, actor=actor, comment="Todo OK")

    assert repository.saved is not None
    assert result.status_id == STATE_IDS["Aprobada"]


@pytest.mark.anyio
async def test_estudiante_recibe_403_al_aprobar() -> None:
    """Estudiante no tiene permisos y recibe 403."""
    internship = _internship("Pendiente")
    repository = FakeInternshipRepository(internship=internship)
    service = InternshipService(internship_repository=repository)

    actor = _user(["Estudiante"])

    with pytest.raises(HTTPException) as exc_info:
        await service.approve(internship_id=1, actor=actor, comment=None)

    assert exc_info.value.status_code == 403


@pytest.mark.anyio
async def test_rechazo_sin_comment_devuelve_400() -> None:
    """Rechazar sin comentario o con puros espacios lanza 400."""
    internship = _internship("Pendiente")
    repository = FakeInternshipRepository(internship=internship)
    service = InternshipService(internship_repository=repository)

    actor = _user(["Encargado de practica"])

    with pytest.raises(HTTPException) as exc_info:
        await service.reject(internship_id=1, actor=actor, comment="   ")  # Forzando .strip()

    assert exc_info.value.status_code == 400


@pytest.mark.anyio
async def test_transicion_invalida_practica_rechazada_lanza_409() -> None:
    """Validar que no se puede aprobar una práctica ya rechazada."""
    internship = _internship("Rechazada")
    repository = FakeInternshipRepository(internship=internship)
    service = InternshipService(internship_repository=repository)

    actor = _user(["Encargado de practica"])

    with pytest.raises(HTTPException) as exc_info:
        await service.approve(internship_id=1, actor=actor, comment=None)

    assert exc_info.value.status_code == 409
    assert "Transición inválida" in exc_info.value.detail