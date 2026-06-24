"""Tests unitarios para las acciones administrativas de practicas.

Cubre las subtareas 6 del issue 9.5:
 - Aprobacion valida directa desde pendiente, En revision y En revision DIRAE
 - Rechazo valido
 - Inicio de revision DIRAE sin modificar estado administrativo
- Rol incorrecto para cada accion (403)
- Comentario faltante en rechazo y derivacion (400)
- Transicion invalida desde estado terminal (409)
- Practica inexistente (404)
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.modules.internships.models.internship_model import (
    CompletionStatusEnum,
    DiraeStatusEnum,
    SchoolInsuranceStatusEnum,
)
from app.modules.internships.services.internship_service import (
    APPROVED_STATUS_TITLE,
    IN_REVIEW_DIRAE_STATUS_TITLE,
    IN_REVIEW_STATUS_TITLE,
    PENDING_STATUS_TITLE,
    REJECTED_STATUS_TITLE,
    InternshipService,
)

def _make_state(title: str, state_id: int = 1) -> MagicMock:
    state = MagicMock()
    state.id = state_id
    state.title = title
    return state


def _make_internship(
    status_title: str | None,
    internship_id: int = 1,
    completion_status=CompletionStatusEnum.not_started,
    dirae_status=DiraeStatusEnum.not_started,
) -> MagicMock:
    internship = MagicMock()
    internship.id = internship_id
    internship.status_id = 1
    internship.status = _make_state(status_title) if status_title else None
    internship.completion_status = completion_status
    internship.dirae_status = dirae_status
    internship.start_date = None
    internship.end_date = None
    internship.insurance_status = SchoolInsuranceStatusEnum.validated
    return internship


def _make_user(*role_names: str) -> MagicMock:
    user = MagicMock()
    user.id = 99
    user.roles = [
        SimpleNamespace(role=SimpleNamespace(name=name))
        for name in role_names
    ]
    return user


def _make_service(
    internship: MagicMock | None = None,
    state_map: dict[str, MagicMock] | None = None,
) -> InternshipService:
    """Construye InternshipService con repositorio completamente mockeado."""

    repo = AsyncMock()
    repo.get_internship_by_id.return_value = internship

    async def _get_state(title: str) -> MagicMock | None:
        return state_map.get(title) if state_map else None

    repo.get_state_by_title.side_effect = _get_state

    async def _update_with_history(
        internship, previous_status, new_status, actor_id, reason, metadata=None
    ):
        internship.status_id = new_status.id
        internship.status = new_status
        return internship

    repo.update_internship_status_with_history.side_effect = _update_with_history

    async def _update_dirae_with_history(
        internship, new_status, actor_id, reason
    ):
        internship.dirae_status = new_status
        return internship

    repo.update_internship_dirae_status_with_history.side_effect = (
        _update_dirae_with_history
    )

    return InternshipService(internship_repository=repo)

class TestApprove:

    @pytest.mark.asyncio
    async def test_encargado_aprueba_desde_pendiente_avanza_a_en_revision(self):
        """Encargado de práctica aprueba desde Pendiente → En revisión."""
        # Agregamos ambos estados al mapa para que el mock los pueda resolver
        state_map = {
            IN_REVIEW_STATUS_TITLE: _make_state(IN_REVIEW_STATUS_TITLE, 2),
            APPROVED_STATUS_TITLE: _make_state(APPROVED_STATUS_TITLE, 3)
        }
        internship = _make_internship(PENDING_STATUS_TITLE)
        service = _make_service(internship=internship, state_map=state_map)
        actor = _make_user("Encargado de practica")

        result = await service.approve(internship.id, actor, comment=None)

        # El flujo por defecto para el Encargado es mover a "En revisión"
        assert result.status.title == IN_REVIEW_STATUS_TITLE

    @pytest.mark.asyncio
    async def test_encargado_no_notifica_aprobacion_al_pasar_a_en_revision(self):
        """Pendiente -> En revisión no debe informar aprobación al estudiante."""
        state_map = {
            IN_REVIEW_STATUS_TITLE: _make_state(IN_REVIEW_STATUS_TITLE, 2),
            APPROVED_STATUS_TITLE: _make_state(APPROVED_STATUS_TITLE, 3),
        }
        internship = _make_internship(PENDING_STATUS_TITLE)
        service = _make_service(internship=internship, state_map=state_map)
        service._dispatch_notification = AsyncMock()
        actor = _make_user("Encargado de practica")

        result = await service.approve(internship.id, actor, comment=None)

        assert result.status.title == IN_REVIEW_STATUS_TITLE
        service._dispatch_notification.assert_not_awaited()
        
    @pytest.mark.asyncio
    async def test_director_aprueba_desde_pendiente_directo_a_aprobada(self):
        """Director de carrera aprueba desde Pendiente → Aprobada directamente (No secuencial)."""
        state_map = {APPROVED_STATUS_TITLE: _make_state(APPROVED_STATUS_TITLE, 3)}
        internship = _make_internship(PENDING_STATUS_TITLE)
        service = _make_service(internship=internship, state_map=state_map)
        actor = _make_user("Director de carrera")

        result = await service.approve(internship.id, actor, comment=None)

        assert result.status.title == APPROVED_STATUS_TITLE

    @pytest.mark.asyncio
    async def test_skip_review_se_conserva_por_compatibilidad(self):
        """skip_review no es requerido, pero se conserva compatible."""
        state_map = {APPROVED_STATUS_TITLE: _make_state(APPROVED_STATUS_TITLE, 3)}
        internship = _make_internship(PENDING_STATUS_TITLE)
        service = _make_service(internship=internship, state_map=state_map)
        actor = _make_user("Encargado de practica")

        result = await service.approve(internship.id, actor, comment=None, skip_review=True)

        assert result.status.title == APPROVED_STATUS_TITLE

    @pytest.mark.asyncio
    async def test_etapa2_en_revision_a_aprobada(self):
        """Cualquier rol autorizado aprueba desde En revisión → Aprobada."""
        state_map = {APPROVED_STATUS_TITLE: _make_state(APPROVED_STATUS_TITLE, 3)}
        internship = _make_internship(IN_REVIEW_STATUS_TITLE)
        service = _make_service(internship=internship, state_map=state_map)
        actor = _make_user("Director de carrera")

        result = await service.approve(internship.id, actor, comment=None)

        assert result.status.title == APPROVED_STATUS_TITLE

    @pytest.mark.asyncio
    async def test_etapa2_desde_en_revision_dirae(self):
        """Director de carrera aprueba desde En revisión DIRAE → Aprobada."""
        state_map = {APPROVED_STATUS_TITLE: _make_state(APPROVED_STATUS_TITLE, 3)}
        internship = _make_internship(IN_REVIEW_DIRAE_STATUS_TITLE)
        service = _make_service(internship=internship, state_map=state_map)
        actor = _make_user("Director de carrera")

        result = await service.approve(internship.id, actor, comment=None)

        assert result.status.title == APPROVED_STATUS_TITLE

    @pytest.mark.asyncio
    async def test_rol_sin_permiso_approve_lanza_403(self):
        """Secretaría de Carrera no puede aprobar."""
        internship = _make_internship(PENDING_STATUS_TITLE)
        service = _make_service(internship=internship)
        actor = _make_user("Secretaria de Carrera")

        with pytest.raises(HTTPException) as exc:
            await service.approve(internship.id, actor, comment=None)

        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_ya_aprobada_lanza_409(self):
        """Aprobar una práctica ya aprobada devuelve 409."""
        internship = _make_internship(APPROVED_STATUS_TITLE)
        service = _make_service(internship=internship)
        actor = _make_user("Director de carrera")

        with pytest.raises(HTTPException) as exc:
            await service.approve(internship.id, actor, comment=None)

        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_inexistente_lanza_404(self):
        """Aprobar una práctica que no existe devuelve 404."""
        service = _make_service(internship=None)
        actor = _make_user("Encargado de practica")

        with pytest.raises(HTTPException) as exc:
            await service.approve(999, actor, comment=None)

        assert exc.value.status_code == 404

class TestReject:

    @pytest.mark.asyncio
    async def test_rechazo_valido_desde_pendiente(self):
        """Encargado de practica rechaza desde Pendiente → Rechazada."""
        state_map = {REJECTED_STATUS_TITLE: _make_state(REJECTED_STATUS_TITLE, 4)}
        internship = _make_internship(PENDING_STATUS_TITLE)
        service = _make_service(internship=internship, state_map=state_map)
        actor = _make_user("Encargado de practica")

        result = await service.reject(internship.id, actor, comment="Documentacion incompleta")

        assert result.status.title == REJECTED_STATUS_TITLE

    @pytest.mark.asyncio
    async def test_rechazo_valido_desde_en_revision(self):
        """Director de carrera rechaza desde En revision → Rechazada."""
        state_map = {REJECTED_STATUS_TITLE: _make_state(REJECTED_STATUS_TITLE, 4)}
        internship = _make_internship(IN_REVIEW_STATUS_TITLE)
        service = _make_service(internship=internship, state_map=state_map)
        actor = _make_user("Director de carrera")

        result = await service.reject(internship.id, actor, comment="No cumple requisitos")

        assert result.status.title == REJECTED_STATUS_TITLE

    @pytest.mark.asyncio
    async def test_sin_comentario_lanza_400(self):
        """Rechazar sin comentario devuelve 400."""
        internship = _make_internship(PENDING_STATUS_TITLE)
        service = _make_service(internship=internship)
        actor = _make_user("Encargado de practica")

        with pytest.raises(HTTPException) as exc:
            await service.reject(internship.id, actor, comment=None)

        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_comentario_en_blanco_lanza_400(self):
        """Rechazar con comentario vacío devuelve 400."""
        internship = _make_internship(PENDING_STATUS_TITLE)
        service = _make_service(internship=internship)
        actor = _make_user("Encargado de practica")

        with pytest.raises(HTTPException) as exc:
            await service.reject(internship.id, actor, comment="   ")

        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_rol_incorrecto_lanza_403(self):
        """Secretaria de Carrera no puede rechazar."""
        internship = _make_internship(PENDING_STATUS_TITLE)
        service = _make_service(internship=internship)
        actor = _make_user("Secretaria de Carrera")

        with pytest.raises(HTTPException) as exc:
            await service.reject(internship.id, actor, comment="Motivo")

        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_ya_rechazada_lanza_409(self):
        """Rechazar una practica ya rechazada devuelve 409."""
        internship = _make_internship(REJECTED_STATUS_TITLE)
        service = _make_service(internship=internship)
        actor = _make_user("Encargado de practica")

        with pytest.raises(HTTPException) as exc:
            await service.reject(internship.id, actor, comment="Motivo")

        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_ya_aprobada_lanza_409(self):
        """Rechazar una practica aprobada devuelve 409."""
        internship = _make_internship(APPROVED_STATUS_TITLE)
        service = _make_service(internship=internship)
        actor = _make_user("Director de carrera")

        with pytest.raises(HTTPException) as exc:
            await service.reject(internship.id, actor, comment="Motivo")

        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_inexistente_lanza_404(self):
        """Rechazar una practica que no existe devuelve 404."""
        service = _make_service(internship=None)
        actor = _make_user("Encargado de practica")

        with pytest.raises(HTTPException) as exc:
            await service.reject(999, actor, comment="Motivo")

        assert exc.value.status_code == 404

class TestDerive:

    @pytest.mark.asyncio
    async def test_derivacion_valida_desde_aprobada_finalizada(self):
        """Secretaria inicia revision DIRAE sin cambiar estado administrativo."""
        internship = _make_internship(
            APPROVED_STATUS_TITLE,
            completion_status=CompletionStatusEnum.finalized,
        )
        service = _make_service(internship=internship)
        actor = _make_user("Secretaria de Carrera")

        result = await service.derive(internship.id, actor, comment="Requiere revision DIRAE")

        assert result.status.title == APPROVED_STATUS_TITLE
        assert result.dirae_status == DiraeStatusEnum.in_review

    @pytest.mark.asyncio
    async def test_derivacion_desde_pendiente_lanza_409(self):
        """No se puede iniciar DIRAE antes de aprobar la solicitud."""
        internship = _make_internship(PENDING_STATUS_TITLE)
        service = _make_service(internship=internship)
        actor = _make_user("Secretaria de Carrera")

        with pytest.raises(HTTPException) as exc:
            await service.derive(internship.id, actor, comment="Se eleva a DIRAE")

        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_derivacion_desde_aprobada_no_finalizada_lanza_409(self):
        """No se puede iniciar DIRAE antes de finalizar la practica."""
        internship = _make_internship(APPROVED_STATUS_TITLE)
        service = _make_service(internship=internship)
        actor = _make_user("Secretaria de Carrera")

        with pytest.raises(HTTPException) as exc:
            await service.derive(internship.id, actor, comment="Se eleva a DIRAE")

        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_sin_comentario_lanza_400(self):
        """Derivar sin comentario devuelve 400."""
        internship = _make_internship(PENDING_STATUS_TITLE)
        service = _make_service(internship=internship)
        actor = _make_user("Secretaria de Carrera")

        with pytest.raises(HTTPException) as exc:
            await service.derive(internship.id, actor, comment=None)

        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_comentario_en_blanco_lanza_400(self):
        """Derivar con comentario vacío devuelve 400."""
        internship = _make_internship(PENDING_STATUS_TITLE)
        service = _make_service(internship=internship)
        actor = _make_user("Secretaria de Carrera")

        with pytest.raises(HTTPException) as exc:
            await service.derive(internship.id, actor, comment="   ")

        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_rol_incorrecto_lanza_403(self):
        """Encargado de practica no puede derivar."""
        internship = _make_internship(PENDING_STATUS_TITLE)
        service = _make_service(internship=internship)
        actor = _make_user("Encargado de practica")

        with pytest.raises(HTTPException) as exc:
            await service.derive(internship.id, actor, comment="Motivo")

        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_dirae_ya_en_revision_lanza_409(self):
        """No se registra dos veces el mismo estado DIRAE."""
        internship = _make_internship(
            APPROVED_STATUS_TITLE,
            completion_status=CompletionStatusEnum.finalized,
            dirae_status=DiraeStatusEnum.in_review,
        )
        service = _make_service(internship=internship)
        actor = _make_user("Secretaria de Carrera")

        with pytest.raises(HTTPException) as exc:
            await service.derive(internship.id, actor, comment="Motivo")

        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_rechazada_lanza_409(self):
        """Derivar una practica rechazada devuelve 409."""
        internship = _make_internship(REJECTED_STATUS_TITLE)
        service = _make_service(internship=internship)
        actor = _make_user("Secretaria de Carrera")

        with pytest.raises(HTTPException) as exc:
            await service.derive(internship.id, actor, comment="Motivo")

        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_inexistente_lanza_404(self):
        """Derivar una practica que no existe devuelve 404."""
        service = _make_service(internship=None)
        actor = _make_user("Secretaria de Carrera")

        with pytest.raises(HTTPException) as exc:
            await service.derive(999, actor, comment="Motivo")

        assert exc.value.status_code == 404


class TestDiraeRectification:

    @pytest.mark.asyncio
    async def test_reapertura_valida_desde_ready_registra_observed(self):
        """Secretaría reabre un expediente listo para rectificación documental."""
        internship = _make_internship(
            APPROVED_STATUS_TITLE,
            completion_status=CompletionStatusEnum.finalized,
            dirae_status=DiraeStatusEnum.ready,
        )
        service = _make_service(internship=internship)
        actor = _make_user("Secretaria de Carrera")

        result = await service.reopen_dirae_rectification(
            internship.id,
            actor,
            reason="Observación documental posterior",
        )

        assert result.status.title == APPROVED_STATUS_TITLE
        assert result.dirae_status == DiraeStatusEnum.observed
        service.internship_repository.update_internship_dirae_status_with_history.assert_awaited_once_with(
            internship=internship,
            new_status=DiraeStatusEnum.observed,
            actor_id=actor.id,
            reason="Observación documental posterior",
        )

    @pytest.mark.asyncio
    async def test_reapertura_valida_desde_exported_registra_observed(self):
        internship = _make_internship(
            APPROVED_STATUS_TITLE,
            completion_status=CompletionStatusEnum.finalized,
            dirae_status=DiraeStatusEnum.exported,
        )
        service = _make_service(internship=internship)
        actor = _make_user("Secretaria de Carrera")

        result = await service.reopen_dirae_rectification(
            internship.id,
            actor,
            reason="Rectificación posterior a exportación",
        )

        assert result.dirae_status == DiraeStatusEnum.observed

    @pytest.mark.asyncio
    async def test_reapertura_exige_comentario(self):
        internship = _make_internship(
            APPROVED_STATUS_TITLE,
            completion_status=CompletionStatusEnum.finalized,
            dirae_status=DiraeStatusEnum.ready,
        )
        service = _make_service(internship=internship)
        actor = _make_user("Secretaria de Carrera")

        with pytest.raises(HTTPException) as exc:
            await service.reopen_dirae_rectification(
                internship.id,
                actor,
                reason=" ",
            )

        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_reapertura_rechaza_estado_no_reabrible(self):
        internship = _make_internship(
            APPROVED_STATUS_TITLE,
            completion_status=CompletionStatusEnum.finalized,
            dirae_status=DiraeStatusEnum.in_review,
        )
        service = _make_service(internship=internship)
        actor = _make_user("Secretaria de Carrera")

        with pytest.raises(HTTPException) as exc:
            await service.reopen_dirae_rectification(
                internship.id,
                actor,
                reason="Motivo",
            )

        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_reapertura_rechaza_rol_sin_permiso(self):
        internship = _make_internship(
            APPROVED_STATUS_TITLE,
            completion_status=CompletionStatusEnum.finalized,
            dirae_status=DiraeStatusEnum.ready,
        )
        service = _make_service(internship=internship)
        actor = _make_user("Encargado de practica")

        with pytest.raises(HTTPException) as exc:
            await service.reopen_dirae_rectification(
                internship.id,
                actor,
                reason="Motivo",
            )

        assert exc.value.status_code == 403
