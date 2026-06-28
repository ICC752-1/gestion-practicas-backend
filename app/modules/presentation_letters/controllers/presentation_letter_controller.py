"""Controlador HTTP para cartas de presentacion automaticas."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import config
from app.core.database.database import get_db
from app.modules.auth.dependencies.auth_dependency import get_current_user
from app.modules.auth.models.user_model import User
from app.modules.notifications.repositories.notification_repository import (
    NotificationRepository,
)
from app.modules.notifications.services.notification_service import (
    NotificationService,
)
from app.modules.presentation_letters.repositories.presentation_letter_repository import (
    PresentationLetterRepository,
)
from app.modules.presentation_letters.schemas.presentation_letter_schema import (
    PresentationLetterGenerateRequest,
    PresentationLetterResponse,
    PresentationLetterTemplateResponse,
    PresentationLetterTemplateUpdateRequest,
)
from app.modules.presentation_letters.services.presentation_letter_service import (
    PresentationLetterService,
)


router = APIRouter(prefix="/presentation-letters", tags=["Presentation Letters"])


def _build_service(db: AsyncSession) -> PresentationLetterService:
    notification_service = NotificationService(
        notification_repository=NotificationRepository(db),
        app_config=config,
    )

    return PresentationLetterService(
        repository=PresentationLetterRepository(db),
        app_config=config,
        notification_service=notification_service,
    )


@router.get(
    "/templates",
    response_model=list[PresentationLetterTemplateResponse],
)
async def list_presentation_letter_templates(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[PresentationLetterTemplateResponse]:
    """Lista plantillas activas para roles administrativos."""

    service = _build_service(db)
    templates = await service.list_templates(actor=current_user)

    return [
        PresentationLetterTemplateResponse.model_validate(template)
        for template in templates
    ]


@router.get(
    "/templates/{practice_type}",
    response_model=PresentationLetterTemplateResponse,
)
async def get_presentation_letter_template(
    practice_type: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PresentationLetterTemplateResponse:
    """Obtiene la plantilla activa para un tipo de practica."""

    service = _build_service(db)
    template = await service.get_template(
        practice_type=practice_type,
        actor=current_user,
    )

    return PresentationLetterTemplateResponse.model_validate(template)


@router.put(
    "/templates/{practice_type}",
    response_model=PresentationLetterTemplateResponse,
)
async def update_presentation_letter_template(
    practice_type: str,
    payload: PresentationLetterTemplateUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PresentationLetterTemplateResponse:
    """Edita una plantilla de carta. Solo Director de carrera."""

    service = _build_service(db)
    template = await service.update_template(
        practice_type=practice_type,
        payload=payload,
        actor=current_user,
    )

    return PresentationLetterTemplateResponse.model_validate(template)


@router.post(
    "/templates/{practice_type}/signature-image",
    response_model=PresentationLetterTemplateResponse,
)
async def upload_presentation_letter_signature_image(
    practice_type: str,
    file: Annotated[UploadFile, File()],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PresentationLetterTemplateResponse:
    """Sube o reemplaza la imagen de firma de una plantilla."""

    service = _build_service(db)
    content = await file.read()
    template = await service.update_template_signature_image(
        practice_type=practice_type,
        file_name=file.filename or "",
        content_type=file.content_type,
        content=content,
        actor=current_user,
    )

    return PresentationLetterTemplateResponse.model_validate(template)


@router.delete(
    "/templates/{practice_type}/signature-image",
    response_model=PresentationLetterTemplateResponse,
)
async def delete_presentation_letter_signature_image(
    practice_type: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PresentationLetterTemplateResponse:
    """Elimina la imagen de firma de una plantilla."""

    service = _build_service(db)
    template = await service.remove_template_signature_image(
        practice_type=practice_type,
        actor=current_user,
    )

    return PresentationLetterTemplateResponse.model_validate(template)


@router.get("/templates/{practice_type}/signature-image")
async def get_presentation_letter_signature_image(
    practice_type: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    """Entrega la imagen de firma configurada para previsualizacion."""

    service = _build_service(db)
    signature = await service.prepare_signature_image(
        practice_type=practice_type,
        actor=current_user,
    )

    return FileResponse(path=str(signature.path), media_type=signature.media_type)


@router.post(
    "/generate",
    response_model=PresentationLetterResponse,
)
async def generate_presentation_letter(
    payload: PresentationLetterGenerateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PresentationLetterResponse:
    """Genera automaticamente una carta PDF para el estudiante autenticado."""

    service = _build_service(db)
    letter = await service.generate_letter(actor=current_user, payload=payload)

    return PresentationLetterResponse.model_validate(letter)


@router.get("/me", response_model=list[PresentationLetterResponse])
async def list_my_presentation_letters(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[PresentationLetterResponse]:
    """Lista cartas generadas del estudiante autenticado."""

    service = _build_service(db)
    letters = await service.list_my_letters(actor=current_user)

    return [PresentationLetterResponse.model_validate(letter) for letter in letters]


@router.get("/{letter_id}/download")
async def download_presentation_letter(
    letter_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    """Descarga autenticada de una carta generada."""

    service = _build_service(db)
    download = await service.prepare_download(
        letter_id=letter_id,
        actor=current_user,
    )

    return FileResponse(
        path=str(download.path),
        filename=download.letter.generated_file_name,
        media_type="application/pdf",
    )
