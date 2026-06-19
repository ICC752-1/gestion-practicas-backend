"""Repositorio de acceso a datos para documentos.

Este modulo encapsula las consultas y operaciones de persistencia del modulo
`documents` usando una sesion asincrona de SQLAlchemy.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models.role_model import Role
from app.modules.auth.models.user_model import User
from app.modules.auth.models.user_role_model import UserRole
from app.modules.documents.models.document_model import (
    Document,
    DocumentStatusEnum,
    DocumentType,
)
from app.modules.internships.models.internship_dirae_status_history_model import (
    InternshipDiraeStatusHistory,
)
from app.modules.internships.models.internship_model import DiraeStatusEnum, Internship


class DocumentRepository:
    """Implementa operaciones de lectura y escritura documental.

    Attributes:
        db: Sesion asincrona utilizada para ejecutar consultas y confirmar
            transacciones.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Inicializa el repositorio con una sesion de base de datos.

        Args:
            db: Sesion asincrona de SQLAlchemy.
        """

        self.db = db

    async def list_active_document_types(self) -> list[DocumentType]:
        """Lista tipos documentales activos.

        Returns:
            Lista de `DocumentType` activos ordenados por identificador.
        """

        query = (
            select(DocumentType)
            .where(DocumentType.is_active.is_(True))
            .order_by(DocumentType.id.asc())
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def get_document_type_by_id(
        self,
        document_type_id: int,
    ) -> DocumentType | None:
        """Obtiene un tipo documental activo por identificador.

        Args:
            document_type_id: Identificador entero del tipo documental.

        Returns:
            `DocumentType` si existe y esta activo; `None` en caso contrario.
        """

        query = select(DocumentType).where(
            DocumentType.id == document_type_id,
            DocumentType.is_active.is_(True),
        )
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def get_internship_by_id(
        self,
        internship_id: int,
    ) -> Internship | None:
        """Obtiene una practica con su estado actual.

        Args:
            internship_id: Identificador entero de la practica.

        Returns:
            `Internship` si existe; `None` en caso contrario.
        """

        query = (
            select(Internship)
            .where(Internship.id == internship_id)
            .options(
                selectinload(Internship.status),
                selectinload(Internship.student),
            )
        )
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def list_required_document_types(self) -> list[DocumentType]:
        """Lista tipos documentales requeridos y activos.

        Returns:
            Lista de `DocumentType` obligatorios para el paquete documental.
        """

        query = (
            select(DocumentType)
            .where(
                DocumentType.is_active.is_(True),
                DocumentType.is_required.is_(True),
            )
            .order_by(DocumentType.id.asc())
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def list_package_documents_by_internship(
        self,
        internship_id: int,
    ) -> list[Document]:
        """Lista documentos candidatos para armar el paquete documental.

        Args:
            internship_id: Identificador entero de la practica.

        Returns:
            Documentos no eliminados con su tipo documental.
        """

        query = (
            select(Document)
            .where(
                Document.internship_id == internship_id,
                Document.deleted_at.is_(None),
                Document.status != DocumentStatusEnum.deleted,
            )
            .options(selectinload(Document.document_type))
            .order_by(
                Document.type_id.asc(),
                Document.upload_date.desc(),
                Document.id.desc(),
            )
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def list_internships_for_dirae_export(
        self,
        internship_ids: list[int] | None = None,
    ) -> list[Internship]:
        """Lista practicas candidatas para exportacion DIRAE.

        Args:
            internship_ids: IDs especificos solicitados. Si es `None`, retorna
                todas las practicas para que el servicio filtre exportables.

        Returns:
            Practicas con estado y estudiante precargados.
        """

        query = select(Internship).options(
            selectinload(Internship.status),
            selectinload(Internship.student),
        )
        if internship_ids is not None:
            query = query.where(Internship.id.in_(internship_ids))

        query = query.order_by(Internship.id.asc())
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def mark_internships_as_dirae_exported(
        self,
        internships: list[Internship],
        actor_id: int,
        reason: str,
    ) -> None:
        """Marca practicas exportadas a DIRAE y registra historial local."""

        for internship in internships:
            previous_status = internship.dirae_status
            internship.dirae_status = DiraeStatusEnum.exported
            self.db.add(
                InternshipDiraeStatusHistory(
                    internship_id=internship.id,
                    previous_status=previous_status,
                    new_status=DiraeStatusEnum.exported,
                    actor_id=actor_id,
                    reason=reason,
                )
            )

        await self.db.commit()

    async def create_document(self, document: Document) -> Document:
        """Persiste un documento.

        Args:
            document: Entidad `Document` a crear.

        Returns:
            Documento persistido y refrescado.
        """

        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)

        loaded_document = await self.get_document_by_id(document.id)
        if loaded_document is None:
            return document

        return loaded_document

    async def list_documents_by_internship(
        self,
        internship_id: int,
    ) -> list[Document]:
        """Lista documentos no eliminados de una practica.

        Args:
            internship_id: Identificador entero de la practica.

        Returns:
            Lista de documentos vigentes ordenados por fecha de carga.
        """

        query = (
            select(Document)
            .where(
                Document.internship_id == internship_id,
                Document.deleted_at.is_(None),
                Document.status != DocumentStatusEnum.deleted,
            )
            .options(selectinload(Document.document_type))
            .order_by(Document.upload_date.desc(), Document.id.desc())
        )
        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def get_document_by_id(self, document_id: int) -> Document | None:
        """Obtiene un documento con relaciones necesarias para permisos.

        Args:
            document_id: Identificador entero del documento.

        Returns:
            `Document` si existe; `None` en caso contrario.
        """

        query = (
            select(Document)
            .where(Document.id == document_id)
            .options(
                selectinload(Document.document_type),
                selectinload(Document.internship).selectinload(Internship.status),
                selectinload(Document.internship).selectinload(
                    Internship.student,
                ),
            )
        )
        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def update_document_status(
        self,
        document: Document,
        new_status: DocumentStatusEnum,
        reviewer_id: int,
        comment: str | None,
    ) -> Document:
        """Actualiza el estado de revision documental.

        Args:
            document: Documento a actualizar.
            new_status: Nuevo estado documental.
            reviewer_id: Usuario que ejecuta la revision.
            comment: Observacion de revision.

        Returns:
            Documento actualizado y refrescado.
        """

        now = datetime.now(UTC).replace(tzinfo=None)
        document.status = new_status
        document.reviewed_at = now
        document.reviewed_by = reviewer_id
        document.review_comment = comment
        document.update_date = now

        await self.db.commit()
        await self.db.refresh(document)

        loaded_document = await self.get_document_by_id(document.id)
        if loaded_document is None:
            return document

        return loaded_document

    async def list_users_by_roles(self, role_names: set[str]) -> list[User]:
        """Lista usuarios activos que poseen alguno de los roles indicados."""

        query = (
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.name.in_(role_names), User.is_active.is_(True))
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .order_by(User.id.asc())
        )
        result = await self.db.execute(query)

        return list(result.scalars().unique().all())

    async def soft_delete_document(
        self,
        document: Document,
        actor_id: int,
    ) -> Document:
        """Marca un documento como eliminado sin borrar sus metadatos.

        Args:
            document: Documento a eliminar logicamente.
            actor_id: Usuario que ejecuta la eliminacion.

        Returns:
            Documento actualizado y refrescado.
        """

        now = datetime.now(UTC).replace(tzinfo=None)
        document.status = DocumentStatusEnum.deleted
        document.deleted_at = now
        document.deleted_by = actor_id
        document.update_date = now

        await self.db.commit()
        await self.db.refresh(document)

        loaded_document = await self.get_document_by_id(document.id)
        if loaded_document is None:
            return document

        return loaded_document
