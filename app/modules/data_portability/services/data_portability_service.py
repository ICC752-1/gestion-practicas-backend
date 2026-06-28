"""Casos de uso para portabilidad de datos del estudiante."""

from datetime import UTC, date, datetime
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import HTTPException, status

from app.core.config import config
from app.modules.auth.models.user_model import User
from app.modules.data_portability.models.data_portability_model import (
    DataPortabilityRequest,
    DataPortabilityStatusEnum,
)
from app.modules.data_portability.repositories.data_portability_repository import (
    DataPortabilityRepository,
)

STUDENT_ROLE = "Estudiante"


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _role_names(user: User) -> set[str]:
    return {user_role.role.name for user_role in user.roles}


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


class DataPortabilityExport:
    """Archivo generado para descarga."""

    def __init__(self, *, filename: str, media_type: str, content: bytes) -> None:
        self.filename = filename
        self.media_type = media_type
        self.content = content


class DataPortabilityService:
    """Construye exportaciones minimizadas sin exponer datos internos."""

    def __init__(
        self,
        repository: DataPortabilityRepository,
        app_config: type | object = config,
    ) -> None:
        self.repository = repository
        self.document_storage_root = Path(
            getattr(app_config, "DOCUMENT_STORAGE_DIR", "storage/documents")
        )

    async def export_my_data(
        self,
        *,
        actor: User,
        export_format: str,
        include_documents: bool,
    ) -> DataPortabilityExport:
        if STUDENT_ROLE not in _role_names(actor):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo estudiantes pueden exportar sus datos personales",
            )
        if export_format not in {"json", "zip"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de exportación no soportado",
            )

        audit = await self.repository.create_request(
            DataPortabilityRequest(
                user_id=actor.id,
                export_format=export_format,
                include_documents=include_documents,
                status=DataPortabilityStatusEnum.processing,
            )
        )

        try:
            payload, documents = await self._build_payload(
                user_id=actor.id,
                include_documents=include_documents,
            )
            metadata = {
                "profile": 1,
                "internships": len(payload["internships"]),
                "status_history": len(payload["status_history"]),
                "exceptions": len(payload["exceptions"]),
                "documents": len(payload["documents"]),
                "self_evaluations": len(payload["self_evaluations"]),
                "supervisor_evaluations": len(payload["supervisor_evaluations"]),
                "included_files": len(documents),
            }
            audit.status = DataPortabilityStatusEnum.completed
            audit.completed_at = _utc_now()
            audit.result_metadata = metadata
            await self.repository.save_request(audit)
        except Exception as exc:
            audit.status = DataPortabilityStatusEnum.failed
            audit.completed_at = _utc_now()
            audit.error_message = str(exc)
            await self.repository.save_request(audit)
            raise

        payload["export_audit"] = {
            "request_id": audit.id,
            "requested_at": _iso(audit.requested_at),
            "completed_at": _iso(audit.completed_at),
            "format": audit.export_format,
            "include_documents": audit.include_documents,
            "result_metadata": metadata,
        }
        timestamp = _utc_now().strftime("%Y%m%d_%H%M%S")
        base_name = f"portabilidad_estudiante_{actor.id}_{timestamp}"
        json_bytes = _json_bytes(payload)

        if export_format == "json":
            return DataPortabilityExport(
                filename=f"{base_name}.json",
                media_type="application/json",
                content=json_bytes,
            )

        buffer = BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("data.json", json_bytes)
            for document_metadata, file_path in documents:
                if file_path.is_file():
                    archive.write(file_path, document_metadata["export_path"])

        return DataPortabilityExport(
            filename=f"{base_name}.zip",
            media_type="application/zip",
            content=buffer.getvalue(),
        )

    async def _build_payload(
        self,
        *,
        user_id: int,
        include_documents: bool,
    ) -> tuple[dict, list[tuple[dict, Path]]]:
        user = await self.repository.get_user(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )

        internships = await self.repository.list_internships(user_id)
        internship_ids = [internship.id for internship in internships]
        history = await self.repository.list_status_history(internship_ids)
        exceptions = await self.repository.list_exceptions(internship_ids)
        documents = await self.repository.list_documents(user_id)
        self_evaluations = await self.repository.list_self_evaluations(user_id)
        supervisor_evaluations = await self.repository.list_supervisor_evaluations(
            internship_ids
        )

        document_payload = []
        document_files: list[tuple[dict, Path]] = []
        for document in documents:
            export_path = (
                f"documents/internship_{document.internship_id}/"
                f"{document.id}_{document.file_name}"
            )
            metadata = {
                "id": document.id,
                "internship_id": document.internship_id,
                "type": document.document_type.name if document.document_type else None,
                "file_name": document.file_name,
                "extension": _enum_value(document.extension),
                "status": _enum_value(document.status),
                "size_bytes": document.size_bytes,
                "upload_date": _iso(document.upload_date),
                "reviewed_at": _iso(document.reviewed_at),
                "review_comment": document.review_comment,
                "included_in_zip": False,
                "export_path": export_path if include_documents else None,
            }
            document_payload.append(metadata)
            if include_documents:
                file_path = self._resolve_document_path(document.file_path)
                metadata["included_in_zip"] = file_path.is_file()
                document_files.append((metadata, file_path))

        payload = {
            "generated_at": _iso(_utc_now()),
            "profile": _user_payload(user),
            "internships": [_internship_payload(item) for item in internships],
            "status_history": [_history_payload(item) for item in history],
            "exceptions": [_exception_payload(item) for item in exceptions],
            "documents": document_payload,
            "self_evaluations": [
                _self_evaluation_payload(item) for item in self_evaluations
            ],
            "supervisor_evaluations": [
                _supervisor_evaluation_payload(item)
                for item in supervisor_evaluations
            ],
        }
        return payload, document_files

    def _resolve_document_path(self, storage_key: str) -> Path:
        root = self.document_storage_root.resolve()
        file_path = (root / storage_key).resolve()
        if root != file_path and root not in file_path.parents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ruta documental inválida",
            )
        return file_path


def _user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "rut": user.rut,
        "enrollment": getattr(user, "enrollment", None),
        "admission_year": getattr(user, "admission_year", None),
        "degree": user.degree,
        "cod_degree": user.cod_degree,
        "sexo": user.sexo,
        "phone": user.phone,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "created_at": _iso(user.created_at),
    }


def _internship_payload(internship) -> dict:
    return {
        "id": internship.id,
        "org_name": internship.org_name,
        "sector": internship.sector,
        "city": internship.city,
        "supervisor_name": internship.supervisor_name,
        "supervisor_profession": internship.supervisor_profession,
        "supervisor_position": internship.supervisor_position,
        "supervisor_department": internship.supervisor_department,
        "supervisor_email": internship.supervisor_email,
        "start_date": _iso(internship.start_date),
        "end_date": _iso(internship.end_date),
        "schedule": internship.schedule,
        "days": internship.days,
        "modality": internship.modality,
        "internship_period": _enum_value(internship.internship_period),
        "internship_type": _enum_value(internship.internship_type),
        "status": internship.status.title if internship.status else None,
        "completion_status": _enum_value(internship.completion_status),
        "final_result": _enum_value(internship.final_result),
        "is_cancelled": internship.is_cancelled,
        "cancellation_reason": internship.cancellation_reason,
        "upload_date": _iso(internship.upload_date),
    }


def _history_payload(history) -> dict:
    return {
        "id": history.id,
        "internship_id": history.internship_id,
        "previous_status": history.previous_status.title if history.previous_status else None,
        "new_status": history.new_status.title if history.new_status else None,
        "reason": history.reason,
        "changed_at": _iso(history.changed_at),
        "metadata": history.metadata_json,
    }


def _exception_payload(exception) -> dict:
    return {
        "id": exception.id,
        "internship_id": exception.internship_id,
        "rule": _enum_value(exception.rule),
        "reason": exception.reason,
        "authorized_at": _iso(exception.authorized_at),
    }


def _self_evaluation_payload(evaluation) -> dict:
    return {
        "id": evaluation.id,
        "internship_id": evaluation.internship_id,
        "form_version": evaluation.form_version,
        "responses": evaluation.responses,
        "observations": evaluation.observations,
        "status": _enum_value(evaluation.status),
        "submitted_at": _iso(evaluation.submitted_at),
        "reopened_at": _iso(evaluation.reopened_at),
        "reopen_reason": evaluation.reopen_reason,
        "updated_at": _iso(evaluation.updated_at),
    }


def _supervisor_evaluation_payload(evaluation) -> dict:
    return {
        "id": evaluation.id,
        "internship_id": evaluation.internship_id,
        "supervisor_name": evaluation.supervisor_name_snapshot,
        "supervisor_email": evaluation.supervisor_email_snapshot,
        "criteria_scores": evaluation.criteria_scores,
        "observations": evaluation.observations,
        "recommendation": evaluation.recommendation,
        "status": evaluation.status,
        "submitted_at": _iso(evaluation.submitted_at),
    }


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
