"""Controlador HTTP para documentos de practica."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import config
from app.core.database.database import get_db
from app.modules.auth.dependencies.auth_dependency import get_current_user
from app.modules.auth.dependencies.role_dependency import require_roles
from app.modules.auth.models.user_model import User
from app.modules.documents.models.document_model import DocumentStatusEnum
from app.modules.documents.repositories.document_repository import (
    DocumentRepository,
)
from app.modules.documents.schemas.document_schema import (
    DocumentPackageResponse,
    DocumentResponse,
    DocumentStatusUpdateRequest,
    DocumentTypeResponse,
)
from app.modules.documents.services.document_service import DocumentService
from app.modules.notifications.repositories.notification_repository import (
    NotificationRepository,
)
from app.modules.notifications.services.notification_service import (
    NotificationService,
)


router = APIRouter(tags=["Documents"])

DOCUMENT_ADMIN_ROLES = [
    "Encargado de practica",
    "Director de carrera",
    "Secretaria de Carrera",
]


def _build_service(db: AsyncSession) -> DocumentService:
    """Construye el servicio documental para un request.

    Args:
        db: Sesion asincrona de SQLAlchemy inyectada por FastAPI.

    Returns:
        Instancia de `DocumentService`.
    """

    notification_service = NotificationService(
        notification_repository=NotificationRepository(db),
        app_config=config,
    )

    return DocumentService(
        document_repository=DocumentRepository(db),
        app_config=config,
        notification_service=notification_service,
    )


@router.get("/documents/types", response_model=list[DocumentTypeResponse])
async def list_document_types(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[DocumentTypeResponse]:
    """Lista tipos documentales activos.

    Args:
        db: Sesion asincrona de base de datos.
        current_user: Usuario autenticado.

    Returns:
        Lista de tipos documentales disponibles.
    """

    service = _build_service(db)
    document_types = await service.list_document_types()

    return [
        DocumentTypeResponse.model_validate(document_type)
        for document_type in document_types
    ]


@router.post(
    "/internships/{internship_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    internship_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    document_type_id: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
) -> DocumentResponse:
    """Carga un documento asociado a una practica.

    Args:
        internship_id: Identificador de la practica asociada.
        db: Sesion asincrona de base de datos.
        current_user: Usuario autenticado.
        document_type_id: Tipo documental seleccionado.
        file: Archivo recibido por multipart.

    Returns:
        Metadatos publicos del documento creado.
    """

    service = _build_service(db)
    content = await file.read()
    document = await service.upload_document(
        internship_id=internship_id,
        document_type_id=document_type_id,
        file_name=file.filename,
        content=content,
        actor=current_user,
    )

    return DocumentResponse.model_validate(document)


@router.get(
    "/internships/{internship_id}/documents",
    response_model=list[DocumentResponse],
)
async def list_internship_documents(
    internship_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[DocumentResponse]:
    """Lista documentos no eliminados de una practica.

    Args:
        internship_id: Identificador de la practica.
        db: Sesion asincrona de base de datos.
        current_user: Usuario autenticado.

    Returns:
        Lista de documentos vigentes.
    """

    service = _build_service(db)
    documents = await service.list_internship_documents(
        internship_id=internship_id,
        actor=current_user,
    )

    return [
        DocumentResponse.model_validate(document)
        for document in documents
    ]


@router.get(
    "/internships/{internship_id}/documents/package",
    response_model=DocumentPackageResponse,
)
async def get_document_package(
    internship_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DocumentPackageResponse:
    """Obtiene el paquete documental de una practica.

    Args:
        internship_id: Identificador de la practica.
        db: Sesion asincrona de base de datos.
        current_user: Usuario autenticado.

    Returns:
        Resumen documental y estado de exportabilidad DIRAE.
    """

    service = _build_service(db)
    package = await service.get_document_package(
        internship_id=internship_id,
        actor=current_user,
    )

    return DocumentPackageResponse.model_validate(package)


@router.get("/dirae/document-packages/export")
async def export_dirae_document_packages(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(DOCUMENT_ADMIN_ROLES))],
    internship_ids: Annotated[list[int] | None, Query()] = None,
) -> Response:
    """Exporta paquetes documentales DIRAE en formato CSV.

    Args:
        db: Sesion asincrona de base de datos.
        current_user: Usuario documental autenticado.
        internship_ids: Practicas especificas a exportar, si aplica.

    Returns:
        CSV con filas exportables o solo encabezado.
    """

    service = _build_service(db)
    export = await service.export_dirae_document_packages(
        actor=current_user,
        internship_ids=internship_ids,
    )

    return Response(
        content=export.content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{export.filename}"'
            )
        },
    )


@router.get("/dirae/document-packages/export/detail")
async def export_dirae_document_packages_detail(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(DOCUMENT_ADMIN_ROLES))],
    internship_ids: Annotated[list[int] | None, Query()] = None,
) -> Response:
    """Exporta CSV de detalle documental por documento para DIRAE.

    Args:
        db: Sesion asincrona de base de datos.
        current_user: Usuario documental autenticado.
        internship_ids: Practicas especificas a exportar, si aplica.

    Returns:
        CSV con una fila por documento aprobado, incluyendo revisor y comentario.
    """

    service = _build_service(db)
    export = await service.export_dirae_document_packages(
        actor=current_user,
        internship_ids=internship_ids,
    )

    return Response(
        content=export.detail_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{export.detail_filename}"'
            )
        },
    )


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    """Descarga un documento mediante endpoint autenticado.

    Args:
        document_id: Identificador del documento.
        db: Sesion asincrona de base de datos.
        current_user: Usuario autenticado.

    Returns:
        Archivo como `FileResponse`.
    """

    service = _build_service(db)
    download = await service.prepare_download(
        document_id=document_id,
        actor=current_user,
    )

    return FileResponse(
        path=str(download.path),
        filename=download.document.file_name,
        media_type="application/octet-stream",
    )


@router.patch(
    "/documents/{document_id}/status",
    response_model=DocumentResponse,
)
async def update_document_status(
    document_id: int,
    payload: DocumentStatusUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(DOCUMENT_ADMIN_ROLES))],
) -> DocumentResponse:
    """Observa o aprueba un documento.

    Args:
        document_id: Identificador del documento.
        payload: Estado destino y comentario.
        db: Sesion asincrona de base de datos.
        current_user: Usuario administrativo autenticado.

    Returns:
        Documento actualizado.
    """

    service = _build_service(db)
    document = await service.update_document_status(
        document_id=document_id,
        new_status=DocumentStatusEnum(payload.status),
        comment=payload.comment,
        actor=current_user,
    )

    return DocumentResponse.model_validate(document)


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    document_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Elimina logicamente un documento.

    Args:
        document_id: Identificador del documento.
        db: Sesion asincrona de base de datos.
        current_user: Usuario autenticado.

    Returns:
        Respuesta 204 sin cuerpo.
    """

    service = _build_service(db)
    await service.soft_delete_document(
        document_id=document_id,
        actor=current_user,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
