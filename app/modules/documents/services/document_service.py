"""Servicios de negocio para documentos de practica."""

from csv import DictWriter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from io import StringIO
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, status

from app.core.config import config
from app.modules.auth.models.user_model import User
from app.modules.documents.models.document_model import (
    Document,
    DocumentCategoryEnum,
    DocumentStatusEnum,
    DocumentType,
)
from app.modules.documents.repositories.document_repository import (
    DocumentRepository,
)
from app.modules.internships.models.internship_model import (
    CompletionStatusEnum,
    DiraeStatusEnum,
    Internship,
)
from app.modules.notifications.services.notification_service import (
    NotificationService,
)
from app.modules.notifications.utils.notification_event_helpers import (
    build_document_status_changed_notification,
    build_document_uploaded_notification,
)


logger = logging.getLogger(__name__)

STUDENT_ROLE = "Estudiante"
DOCUMENT_ADMIN_ROLES = {
    "Encargado de practica",
    "Director de carrera",
    "Secretaria de Carrera",
}
SECRETARY_ROLE = "Secretaria de Carrera"
TERMINAL_INTERNSHIP_STATES = {"Aprobada", "Rechazada", "Reprobada"}
APPROVED_INTERNSHIP_STATE = "Aprobada"
REASON_INTERNSHIP_NOT_APPROVED = "internship_not_approved"
REASON_PRACTICE_NOT_FINALIZED = "practice_not_finalized"
REASON_DIRAE_NOT_READY = "dirae_not_ready"
REASON_MISSING_REQUIRED_DOCUMENTS = "missing_required_documents"
REASON_OBSERVED_DOCUMENTS_PENDING = "observed_documents_pending"
REASON_SENSITIVE_DOCUMENT_RESTRICTED = "sensitive_document_restricted"
PACKAGE_DOCUMENT_APPROVED = "approved"
PACKAGE_DOCUMENT_MISSING = "missing"
DIRAE_EXPORTED_REASON = "dirae_document_package_exported"
DIRAE_CSV_HEADER = [
    "internship_id",
    "student_id",
    "student_rut",
    "student_enrollment",
    "student_first_name",
    "student_last_name",
    "student_email",
    "degree",
    "cod_degree",
    "internship_type",
    "internship_period",
    "organization",
    "city",
    "start_date",
    "end_date",
    "approved_document_ids",
    "required_document_type_ids",
    "exported_at",
]


@dataclass(frozen=True)
class DocumentDownload:
    """Datos necesarios para descargar un documento autorizado."""

    document: Document
    path: Path


@dataclass(frozen=True)
class DocumentPackageStudent:
    """Datos del estudiante incluidos en el paquete documental."""

    id: int | None
    rut: str | None
    enrollment: str | None
    first_name: str | None
    last_name: str | None
    email: str | None
    degree: str | None
    cod_degree: str | None


@dataclass(frozen=True)
class DocumentPackageInternship:
    """Datos de la practica incluidos en el paquete documental."""

    type: str | None
    period: str | None
    organization: str | None
    city: str | None
    start_date: date | None
    end_date: date | None


@dataclass(frozen=True)
class DocumentPackageItem:
    """Documento seleccionado o faltante dentro del paquete."""

    type_id: int
    type_name: str
    status: str
    document: Document | None


@dataclass(frozen=True)
class DocumentPackage:
    """Resumen documental de una practica para DIRAE."""

    internship_id: int
    status: str | None
    dirae_status: DiraeStatusEnum
    exportable: bool
    reasons: list[str]
    student: DocumentPackageStudent
    internship: DocumentPackageInternship
    required_documents: list[DocumentPackageItem]
    optional_documents: list[DocumentPackageItem]


@dataclass(frozen=True)
class DiraeExportAuditEvent:
    """Evento estructurado para integrar auditoria de exportacion DIRAE."""

    name: str
    actor_id: int | None
    internship_ids: list[int]
    approved_document_ids: list[int]
    filename: str
    exported_at: datetime
    result: str


@dataclass(frozen=True)
class DiraeDocumentPackageExport:
    """Contenido generado para exportacion CSV DIRAE."""

    filename: str
    content: str
    audit_event: DiraeExportAuditEvent


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
        notification_service: NotificationService | None = None,
    ) -> None:
        """Inicializa el servicio con repositorio y configuracion.

        Args:
            document_repository: Repositorio de documentos.
            app_config: Configuracion de aplicacion o doble de pruebas.
            notification_service: Servicio opcional para despachar eventos.
        """

        self.repository = document_repository
        self.notification_service = notification_service
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
        document_type = await self.repository.get_document_type_by_id(
            document_type_id,
        )
        if document_type is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document type not found",
            )

        await self._require_upload_permission(actor, internship, document_type)

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
            created_document = await self.repository.create_document(document)
        except Exception:
            stored_path.unlink(missing_ok=True)
            raise

        await self._dispatch_document_uploaded_notifications(created_document)

        return created_document

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

        documents = await self.repository.list_documents_by_internship(internship_id)

        return self._filter_accessible_documents(actor, documents)

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
        self._require_sensitive_document_access(actor, document)

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

        updated_document = await self.repository.update_document_status(
            document=document,
            new_status=new_status,
            reviewer_id=actor.id,
            comment=None if comment is None else comment.strip(),
        )

        await self._dispatch_document_status_notification(updated_document)

        return updated_document

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

    async def get_document_package(
        self,
        internship_id: int,
        actor: User,
    ) -> DocumentPackage:
        """Obtiene el resumen documental de una practica.

        Args:
            internship_id: Identificador de la practica.
            actor: Usuario autenticado que consulta.

        Returns:
            Paquete documental con estado de exportabilidad.
        """

        internship = await self._get_internship_or_404(internship_id)
        self._require_read_access(actor, internship)

        return await self._build_document_package(internship, actor=actor)

    async def export_dirae_document_packages(
        self,
        actor: User,
        internship_ids: list[int] | None = None,
    ) -> DiraeDocumentPackageExport:
        """Genera CSV con paquetes documentales exportables a DIRAE.

        Args:
            actor: Usuario documental autorizado.
            internship_ids: Practicas especificas solicitadas.

        Returns:
            CSV y nombre de archivo sugerido.
        """

        self._require_document_admin(actor)

        requested_ids = list(dict.fromkeys(internship_ids or []))
        requested_filter = requested_ids or None
        internships = await self.repository.list_internships_for_dirae_export(
            requested_filter,
        )

        if requested_filter is not None:
            self._validate_requested_internships_exist(
                requested_ids,
                internships,
            )

        required_types = await self.repository.list_required_document_types()
        packages = []
        not_exportable_packages = []
        for internship in internships:
            package = await self._build_document_package(
                internship,
                required_types=required_types,
                actor=actor,
            )
            if package.exportable:
                packages.append(package)
            elif requested_filter is not None:
                not_exportable_packages.append(package)

        if not_exportable_packages:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Some internships are not exportable to DIRAE",
                    "internships": [
                        {
                            "internship_id": package.internship_id,
                            "reasons": package.reasons,
                        }
                        for package in not_exportable_packages
                    ],
                },
            )

        exported_at = datetime.now(UTC).replace(microsecond=0)
        filename = (
            "dirae_document_packages_"
            f"{exported_at:%Y%m%d_%H%M%S}.csv"
        )
        content = self._build_dirae_csv(packages, exported_at)
        audit_event = self._build_dirae_export_audit_event(
            packages=packages,
            actor=actor,
            filename=filename,
            exported_at=exported_at,
        )

        if packages:
            packages_by_id = {package.internship_id: package for package in packages}
            await self.repository.mark_internships_as_dirae_exported(
                [
                    internship
                    for internship in internships
                    if internship.id in packages_by_id
                ],
                actor.id,
                DIRAE_EXPORTED_REASON,
            )

        return DiraeDocumentPackageExport(
            filename=filename,
            content=content,
            audit_event=audit_event,
        )

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

    async def _build_document_package(
        self,
        internship: Internship,
        required_types: list[DocumentType] | None = None,
        actor: User | None = None,
    ) -> DocumentPackage:
        if required_types is None:
            required_types = await self.repository.list_required_document_types()

        documents = await self.repository.list_package_documents_by_internship(
            internship.id,
        )
        sensitive_restricted = self._has_sensitive_restriction(
            actor,
            documents,
            required_types,
        )
        documents = self._filter_accessible_documents(actor, documents)
        required_types = self._filter_accessible_document_types(actor, required_types)
        selected_documents = self._select_latest_approved_documents(documents)
        observed_documents_pending = self._has_observed_documents_pending(documents)
        required_type_ids = {document_type.id for document_type in required_types}
        required_documents = []
        missing_required = False

        for document_type in required_types:
            document = selected_documents.get(document_type.id)
            if document is None:
                missing_required = True
                required_documents.append(
                    DocumentPackageItem(
                        type_id=document_type.id,
                        type_name=document_type.name,
                        status=PACKAGE_DOCUMENT_MISSING,
                        document=None,
                    )
                )
                continue

            required_documents.append(
                DocumentPackageItem(
                    type_id=document_type.id,
                    type_name=document_type.name,
                    status=PACKAGE_DOCUMENT_APPROVED,
                    document=document,
                )
            )

        optional_documents = [
            DocumentPackageItem(
                type_id=document.type_id,
                type_name=document.document_type.name,
                status=PACKAGE_DOCUMENT_APPROVED,
                document=document,
            )
            for document in selected_documents.values()
            if document.type_id not in required_type_ids
            and document.document_type is not None
        ]

        reasons = self._get_package_reasons(
            internship,
            missing_required,
            observed_documents_pending,
            sensitive_restricted,
        )

        return DocumentPackage(
            internship_id=internship.id,
            status=self._get_internship_status_title(internship),
            dirae_status=getattr(
                internship,
                "dirae_status",
                DiraeStatusEnum.not_started,
            ),
            exportable=len(reasons) == 0,
            reasons=reasons,
            student=self._build_student_summary(internship),
            internship=self._build_internship_summary(internship),
            required_documents=required_documents,
            optional_documents=optional_documents,
        )

    def _select_latest_approved_documents(
        self,
        documents: list[Document],
    ) -> dict[int, Document]:
        selected_documents = {}
        approved_documents = [
            document
            for document in documents
            if self._is_package_approved_document(document)
        ]
        approved_documents.sort(key=self._document_sort_key, reverse=True)

        for document in approved_documents:
            if document.type_id not in selected_documents:
                selected_documents[document.type_id] = document

        return selected_documents

    def _is_package_approved_document(self, document: Document) -> bool:
        return (
            document.status == DocumentStatusEnum.approved
            and document.deleted_at is None
            and document.status != DocumentStatusEnum.deleted
        )

    def _has_observed_documents_pending(self, documents: list[Document]) -> bool:
        return any(
            document.status == DocumentStatusEnum.observed
            and document.deleted_at is None
            for document in documents
        )

    def _get_package_reasons(
        self,
        internship: Internship,
        missing_required: bool,
        observed_documents_pending: bool,
        sensitive_restricted: bool,
    ) -> list[str]:
        reasons = []
        if self._get_internship_status_title(internship) != APPROVED_INTERNSHIP_STATE:
            reasons.append(REASON_INTERNSHIP_NOT_APPROVED)

        if getattr(internship, "completion_status", None) != CompletionStatusEnum.finalized:
            reasons.append(REASON_PRACTICE_NOT_FINALIZED)

        if getattr(internship, "dirae_status", DiraeStatusEnum.not_started) != DiraeStatusEnum.ready:
            reasons.append(REASON_DIRAE_NOT_READY)

        if missing_required:
            reasons.append(REASON_MISSING_REQUIRED_DOCUMENTS)

        if observed_documents_pending:
            reasons.append(REASON_OBSERVED_DOCUMENTS_PENDING)

        if sensitive_restricted:
            reasons.append(REASON_SENSITIVE_DOCUMENT_RESTRICTED)

        return reasons

    def _filter_accessible_documents(
        self,
        actor: User | None,
        documents: list[Document],
    ) -> list[Document]:
        if not self._is_secretary(actor):
            return documents

        return [
            document
            for document in documents
            if not self._is_sensitive_document(document)
        ]

    def _filter_accessible_document_types(
        self,
        actor: User | None,
        document_types: list[DocumentType],
    ) -> list[DocumentType]:
        if not self._is_secretary(actor):
            return document_types

        return [
            document_type
            for document_type in document_types
            if not self._is_sensitive_document_type(document_type)
        ]

    def _has_sensitive_restriction(
        self,
        actor: User | None,
        documents: list[Document],
        required_types: list[DocumentType],
    ) -> bool:
        if not self._is_secretary(actor):
            return False

        return any(
            self._is_sensitive_document(document)
            and document.deleted_at is None
            and document.status != DocumentStatusEnum.deleted
            for document in documents
        ) or any(
            self._is_sensitive_document_type(document_type)
            for document_type in required_types
        )

    def _require_sensitive_document_access(
        self,
        actor: User,
        document: Document,
    ) -> None:
        if self._is_secretary(actor) and self._is_sensitive_document(document):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

    def _is_secretary(self, actor: User | None) -> bool:
        return actor is not None and self._has_any_role(actor, {SECRETARY_ROLE})

    def _is_sensitive_document(self, document: Document) -> bool:
        return self._is_sensitive_document_type(document.document_type)

    def _is_sensitive_document_type(self, document_type: DocumentType | None) -> bool:
        return bool(getattr(document_type, "is_sensitive", False))

    def _build_student_summary(
        self,
        internship: Internship,
    ) -> DocumentPackageStudent:
        student = internship.student

        return DocumentPackageStudent(
            id=getattr(student, "id", internship.user_id),
            rut=getattr(student, "rut", None),
            enrollment=self._build_student_enrollment(student),
            first_name=getattr(student, "first_name", None),
            last_name=getattr(student, "last_name", None),
            email=getattr(student, "email", None),
            degree=getattr(student, "degree", None),
            cod_degree=getattr(student, "cod_degree", None),
        )

    def _build_internship_summary(
        self,
        internship: Internship,
    ) -> DocumentPackageInternship:
        return DocumentPackageInternship(
            type=self._string_value(internship.internship_type),
            period=self._string_value(internship.internship_period),
            organization=internship.org_name,
            city=internship.city,
            start_date=internship.start_date,
            end_date=internship.end_date,
        )

    def _validate_requested_internships_exist(
        self,
        requested_ids: list[int],
        internships: list[Internship],
    ) -> None:
        found_ids = {internship.id for internship in internships}
        missing_ids = [
            internship_id
            for internship_id in requested_ids
            if internship_id not in found_ids
        ]
        if not missing_ids:
            return

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "Internship not found",
                "internship_ids": missing_ids,
            },
        )

    def _build_dirae_csv(
        self,
        packages: list[DocumentPackage],
        exported_at: datetime,
    ) -> str:
        output = StringIO()
        writer = DictWriter(
            output,
            fieldnames=DIRAE_CSV_HEADER,
            lineterminator="\n",
        )
        writer.writeheader()
        exported_at_value = exported_at.isoformat().replace("+00:00", "Z")

        for package in packages:
            approved_documents = [
                item.document
                for item in package.required_documents
                if item.document is not None
            ]
            writer.writerow(
                {
                    "internship_id": package.internship_id,
                    "student_id": self._csv_value(package.student.id),
                    "student_rut": self._csv_value(package.student.rut),
                    "student_enrollment": self._csv_value(
                        package.student.enrollment,
                    ),
                    "student_first_name": self._csv_value(
                        package.student.first_name,
                    ),
                    "student_last_name": self._csv_value(
                        package.student.last_name,
                    ),
                    "student_email": self._csv_value(package.student.email),
                    "degree": self._csv_value(package.student.degree),
                    "cod_degree": self._csv_value(package.student.cod_degree),
                    "internship_type": self._csv_value(package.internship.type),
                    "internship_period": self._csv_value(
                        package.internship.period,
                    ),
                    "organization": self._csv_value(
                        package.internship.organization,
                    ),
                    "city": self._csv_value(package.internship.city),
                    "start_date": self._csv_value(
                        package.internship.start_date,
                    ),
                    "end_date": self._csv_value(package.internship.end_date),
                    "approved_document_ids": ";".join(
                        str(document.id)
                        for document in approved_documents
                    ),
                    "required_document_type_ids": ";".join(
                        str(item.type_id)
                        for item in package.required_documents
                    ),
                    "exported_at": exported_at_value,
                }
            )

        return output.getvalue()

    def _build_student_enrollment(self, student: object | None) -> str | None:
        if student is None:
            return None

        rut = getattr(student, "rut", None)
        admission_year = self._get_student_admission_year(student)
        if rut is None or admission_year is None:
            return None

        rut_value = "".join(
            character
            for character in str(rut).upper()
            if character.isdigit() or character == "K"
        )
        year_value = "".join(
            character
            for character in str(admission_year)
            if character.isdigit()
        )
        if not rut_value or len(year_value) < 2:
            return None

        return f"{rut_value}{year_value[-2:]}"

    def _get_student_admission_year(self, student: object) -> object | None:
        for field_name in (
            "admission_year",
            "entry_year",
            "enrollment_year",
        ):
            value = getattr(student, field_name, None)
            if value is not None:
                return value

        return None

    def _build_dirae_export_audit_event(
        self,
        *,
        packages: list[DocumentPackage],
        actor: User,
        filename: str,
        exported_at: datetime,
    ) -> DiraeExportAuditEvent:
        approved_document_ids = [
            item.document.id
            for package in packages
            for item in package.required_documents
            if item.document is not None
        ]

        return DiraeExportAuditEvent(
            name="dirae_export_generated",
            actor_id=getattr(actor, "id", None),
            internship_ids=[package.internship_id for package in packages],
            approved_document_ids=approved_document_ids,
            filename=filename,
            exported_at=exported_at,
            result="generated",
        )

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

    async def _require_upload_permission(
        self,
        actor: User,
        internship: Internship,
        document_type: DocumentType,
    ) -> None:
        if internship.user_id == actor.id:
            await self._require_student_upload_permission(internship, document_type)
            return

        if self._is_secretary(actor):
            self._require_secretary_upload_permission(internship, document_type)
            return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    async def _require_student_upload_permission(
        self,
        internship: Internship,
        document_type: DocumentType,
    ) -> None:
        status_title = self._get_internship_status_title(internship)
        if status_title not in TERMINAL_INTERNSHIP_STATES:
            return

        if (
            status_title == APPROVED_INTERNSHIP_STATE
            and await self._has_observed_document_for_type(
                internship.id,
                document_type.id,
            )
        ):
            return

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Cannot upload documents for an internship in terminal "
                f"state: {status_title}"
            ),
        )

    def _require_secretary_upload_permission(
        self,
        internship: Internship,
        document_type: DocumentType,
    ) -> None:
        if self._get_internship_status_title(internship) != APPROVED_INTERNSHIP_STATE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Administrative document correction requires an approved internship request.",
            )

        if (
            document_type.category != DocumentCategoryEnum.administrative
            or self._is_sensitive_document_type(document_type)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

    async def _has_observed_document_for_type(
        self,
        internship_id: int,
        document_type_id: int,
    ) -> bool:
        documents = await self.repository.list_documents_by_internship(internship_id)

        return any(
            document.type_id == document_type_id
            and document.status == DocumentStatusEnum.observed
            and document.deleted_at is None
            for document in documents
        )

    def _require_uploadable_internship(self, internship: Internship) -> None:
        status_title = self._get_internship_status_title(internship)

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

    def _get_internship_status_title(
        self,
        internship: Internship,
    ) -> str | None:
        if internship.status is None:
            return None

        return internship.status.title

    def _document_sort_key(self, document: Document) -> tuple[datetime, int]:
        return (
            document.upload_date or datetime.min,
            document.id or 0,
        )

    def _csv_value(self, value: object) -> str:
        if value is None:
            return ""

        if isinstance(value, date | datetime):
            return value.isoformat()

        return self._string_value(value) or ""

    def _string_value(self, value: object) -> str | None:
        if value is None:
            return None

        enum_value = getattr(value, "value", None)
        if enum_value is not None:
            return str(enum_value)

        return str(value)

    async def _dispatch_document_uploaded_notifications(
        self,
        document: Document,
    ) -> None:
        """Notifica a revisores que existe un documento pendiente."""

        if self.notification_service is None:
            return

        recipients = await self.repository.list_users_by_roles(DOCUMENT_ADMIN_ROLES)
        for recipient in recipients:
            await self._dispatch_notification(
                build_document_uploaded_notification(
                    recipient_user_id=recipient.id,
                    recipient_email=recipient.email,
                    document_id=document.id,
                    internship_id=document.internship_id,
                    document_type=document.document_type.name,
                    file_name=document.file_name,
                    org_name=document.internship.org_name,
                ),
            )

    async def _dispatch_document_status_notification(
        self,
        document: Document,
    ) -> None:
        """Notifica al estudiante cuando un documento es revisado."""

        if self.notification_service is None:
            return

        student_email = None
        if document.internship.student is not None:
            student_email = document.internship.student.email

        document_status = document.status
        if isinstance(document_status, DocumentStatusEnum):
            document_status = document_status.value

        await self._dispatch_notification(
            build_document_status_changed_notification(
                recipient_user_id=document.user_id,
                recipient_email=student_email,
                document_id=document.id,
                internship_id=document.internship_id,
                document_type=document.document_type.name,
                new_status=document_status,
                comment=document.review_comment,
            ),
        )

    async def _dispatch_notification(self, notification) -> None:
        """Despacha una notificacion sin interrumpir el flujo documental."""

        if self.notification_service is None:
            return

        try:
            await self.notification_service.create_and_dispatch(notification)
        except Exception:
            logger.warning(
                "Fallo al despachar notificacion documental (event=%s). "
                "El flujo de negocio continua normalmente.",
                notification.event_type,
                exc_info=True,
            )

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
