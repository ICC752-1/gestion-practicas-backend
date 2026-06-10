"""Servicios de negocio para documentos de practica."""

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, status

from app.core.config import config
from app.modules.auth.models.user_model import User
from app.modules.documents.models.document_model import (
    Document,
    DocumentStatusEnum,
    DocumentType,
)
from app.modules.documents.repositories.document_repository import (
    DocumentRepository,
)
from app.modules.internships.models.internship_model import Internship


STUDENT_ROLE = "Estudiante"
DOCUMENT_ADMIN_ROLES = {
    "Encargado de practica",
    "Director de carrera",
    "Secretaria de Carrera",
}
TERMINAL_INTERNSHIP_STATES = {"Aprobada", "Rechazada", "Reprobada"}


@dataclass(frozen=True)
class DocumentDownload:
    """Datos necesarios para descargar un documento autorizado."""

    document: Document
    path: Path


class DocumentService:
    """Orquesta casos de uso del modulo documental.

    Attributes:
        repository: Repositorio documental.
        storage_root: Directorio base de storage privado.
        max_bytes: Peso maximo permitido por archivo.
        allowed_extensions: Extensiones permitidas normalizadas.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        app_config: type | object = config,
    ) -> None:
        """Inicializa el servicio con repositorio y configuracion.

        Args:
            document_repository: Repositorio de documentos.
            app_config: Configuracion de aplicacion o doble de pruebas.
        """

        self.repository = document_repository
        self.storage_root = Path(
            getattr(app_config, "DOCUMENT_STORAGE_DIR", "storage/documents")
        )
        self.max_bytes = int(getattr(app_config, "DOCUMENT_MAX_BYTES", 10485760))
        self.allowed_extensions = self._get_allowed_extensions(app_config)

    async def list_document_types(self) -> list[DocumentType]:
        """Lista tipos documentales activos.

        Returns:
            Lista de tipos documentales disponibles para carga.
        """

        return await self.repository.list_active_document_types()

    async def upload_document(
        self,
        internship_id: int,
        document_type_id: int,
        file_name: str | None,
        content: bytes,
        actor: User,
    ) -> Document:
        """Carga un documento asociado a una practica.

        Args:
            internship_id: Practica asociada.
            document_type_id: Tipo documental seleccionado.
            file_name: Nombre original recibido desde `UploadFile`.
            content: Contenido binario del archivo.
            actor: Usuario autenticado que realiza la carga.

        Returns:
            Documento persistido.

        Raises:
            HTTPException: Con codigos 400, 403, 404 o 409 segun la regla
                incumplida.
        """

        internship = await self._get_internship_or_404(internship_id)
        self._require_owner(actor, internship)
        self._require_uploadable_internship(internship)

        document_type = await self.repository.get_document_type_by_id(
            document_type_id,
        )
        if document_type is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document type not found",
            )

        normalized_name = self._normalize_file_name(file_name)
        extension = self._validate_extension(normalized_name)
        size_bytes = self._validate_size(content)
        storage_key = self._build_storage_key(internship_id, extension)
        stored_path = self._write_file(storage_key, content)

        document = Document(
            file_name=normalized_name,
            file_path=storage_key,
            extension=extension,
            status=DocumentStatusEnum.uploaded,
            size_bytes=size_bytes,
            internship_id=internship_id,
            type_id=document_type.id,
            user_id=actor.id,
        )

        try:
            return await self.repository.create_document(document)
        except Exception:
            stored_path.unlink(missing_ok=True)
            raise

    async def list_internship_documents(
        self,
        internship_id: int,
        actor: User,
    ) -> list[Document]:
        """Lista documentos vigentes de una practica.

        Args:
            internship_id: Identificador de la practica.
            actor: Usuario autenticado que consulta.

        Returns:
            Lista de documentos no eliminados.
        """

        internship = await self._get_internship_or_404(internship_id)
        self._require_read_access(actor, internship)

        return await self.repository.list_documents_by_internship(internship_id)

    async def prepare_download(
        self,
        document_id: int,
        actor: User,
    ) -> DocumentDownload:
        """Prepara la descarga de un documento autorizado.

        Args:
            document_id: Identificador del documento.
            actor: Usuario autenticado que solicita la descarga.

        Returns:
            `DocumentDownload` con metadatos y ruta local.
        """

        document = await self._get_document_or_404(document_id)
        self._require_not_deleted(document)
        self._require_read_access(actor, document.internship)

        file_path = self._resolve_storage_key(document.file_path)
        if not file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document file not found",
            )

        return DocumentDownload(document=document, path=file_path)

    async def update_document_status(
        self,
        document_id: int,
        new_status: DocumentStatusEnum,
        comment: str | None,
        actor: User,
    ) -> Document:
        """Actualiza el estado documental tras revision administrativa.

        Args:
            document_id: Identificador del documento.
            new_status: Estado destino permitido.
            comment: Observacion de revision.
            actor: Usuario administrativo que revisa.

        Returns:
            Documento actualizado.
        """

        self._require_document_admin(actor)
        self._validate_review_payload(new_status, comment)

        document = await self._get_document_or_404(document_id)
        self._require_not_deleted(document)

        return await self.repository.update_document_status(
            document=document,
            new_status=new_status,
            reviewer_id=actor.id,
            comment=None if comment is None else comment.strip(),
        )

    async def soft_delete_document(
        self,
        document_id: int,
        actor: User,
    ) -> Document:
        """Elimina logicamente un documento.

        Args:
            document_id: Identificador del documento.
            actor: Usuario autenticado que elimina.

        Returns:
            Documento marcado como eliminado.
        """

        document = await self._get_document_or_404(document_id)
        self._require_not_deleted(document)

        if self._has_any_role(actor, DOCUMENT_ADMIN_ROLES):
            return await self.repository.soft_delete_document(document, actor.id)

        self._require_owner(actor, document.internship)
        if document.status == DocumentStatusEnum.approved:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Approved documents cannot be deleted by the student",
            )

        return await self.repository.soft_delete_document(document, actor.id)

    async def _get_internship_or_404(self, internship_id: int) -> Internship:
        internship = await self.repository.get_internship_by_id(internship_id)
        if internship is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Internship not found",
            )

        return internship

    async def _get_document_or_404(self, document_id: int) -> Document:
        document = await self.repository.get_document_by_id(document_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        return document

    def _require_owner(self, actor: User, internship: Internship) -> None:
        if internship.user_id != actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

    def _require_read_access(self, actor: User, internship: Internship) -> None:
        if internship.user_id == actor.id:
            return

        if self._has_any_role(actor, DOCUMENT_ADMIN_ROLES):
            return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    def _require_document_admin(self, actor: User) -> None:
        if not self._has_any_role(actor, DOCUMENT_ADMIN_ROLES):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

    def _require_uploadable_internship(self, internship: Internship) -> None:
        status_title = None
        if internship.status is not None:
            status_title = internship.status.title

        if status_title in TERMINAL_INTERNSHIP_STATES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Cannot upload documents for an internship in terminal "
                    f"state: {status_title}"
                ),
            )

    def _require_not_deleted(self, document: Document) -> None:
        if (
            document.deleted_at is not None
            or document.status == DocumentStatusEnum.deleted
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

    def _validate_review_payload(
        self,
        new_status: DocumentStatusEnum,
        comment: str | None,
    ) -> None:
        if new_status not in {
            DocumentStatusEnum.observed,
            DocumentStatusEnum.approved,
        }:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid document status",
            )

        if new_status == DocumentStatusEnum.observed and (
            comment is None or not comment.strip()
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A comment is required when observing a document",
            )

    def _normalize_file_name(self, file_name: str | None) -> str:
        if file_name is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File name is required",
            )

        normalized = Path(file_name).name.strip()
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File name is required",
            )

        return normalized[:255]

    def _validate_extension(self, file_name: str) -> str:
        extension = Path(file_name).suffix.lower().lstrip(".")
        if not extension or extension not in self.allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid document extension",
            )

        return extension

    def _validate_size(self, content: bytes) -> int:
        size_bytes = len(content)
        if size_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document file cannot be empty",
            )

        if size_bytes > self.max_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document file exceeds maximum size",
            )

        return size_bytes

    def _build_storage_key(self, internship_id: int, extension: str) -> str:
        return f"{internship_id}/{uuid4().hex}.{extension}"

    def _write_file(self, storage_key: str, content: bytes) -> Path:
        file_path = self._resolve_storage_key(storage_key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)

        return file_path

    def _resolve_storage_key(self, storage_key: str) -> Path:
        storage_path = Path(storage_key)
        if storage_path.is_absolute() or ".." in storage_path.parts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid document storage key",
            )

        return self.storage_root / storage_path

    def _get_allowed_extensions(self, app_config: type | object) -> set[str]:
        extension_set = getattr(
            app_config,
            "DOCUMENT_ALLOWED_EXTENSION_SET",
            None,
        )
        if extension_set is not None:
            return set(extension_set)

        raw_extensions = getattr(
            app_config,
            "DOCUMENT_ALLOWED_EXTENSIONS",
            "pdf,docx,jpg,png,zip",
        )

        return {
            extension.strip().lower().lstrip(".")
            for extension in raw_extensions.split(",")
            if extension.strip()
        }

    @staticmethod
    def _has_any_role(actor: User, role_names: set[str]) -> bool:
        return any(
            user_role.role.name in role_names
            for user_role in actor.roles
        )
