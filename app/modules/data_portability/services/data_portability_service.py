"""Casos de uso para portabilidad de datos del estudiante."""

from datetime import UTC, date, datetime
from hashlib import sha256
from html import escape
from io import BytesIO
import json
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import HTTPException, status
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

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
PDF_VALUE_LABELS = {
    "approved": "Aprobado",
    "cancelled": "Cancelado",
    "completed": "Completado",
    "failed": "Reprobado",
    "finalized": "Finalizada",
    "in_progress": "En ejecución",
    "not_started": "No iniciada",
    "observed": "Observado",
    "passed": "Aprobada",
    "pending": "Pendiente",
    "related_actor": "Actor relacionado",
    "student": "Estudiante",
    "uploaded": "Cargado",
    "valid": "Vigente",
}


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
        self.presentation_letter_storage_root = Path(
            getattr(
                app_config,
                "PRESENTATION_LETTER_STORAGE_DIR",
                "storage/presentation_letters",
            )
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
        if export_format not in {"json", "pdf", "zip"}:
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
            payload, archive_files = await self._build_payload(
                user_id=actor.id,
                include_documents=include_documents,
            )
            metadata = {
                "profile": 1,
                "internships": len(payload["internships"]),
                "status_history": len(payload["status_history"]),
                "exceptions": len(payload["exceptions"]),
                "documents": len(payload["documents"]),
                "presentation_letters": len(payload["presentation_letters"]),
                "self_evaluations": len(payload["self_evaluations"]),
                "supervisor_evaluations": len(payload["supervisor_evaluations"]),
                "included_files": sum(
                    1 for _, file_path in archive_files if file_path.is_file()
                ),
            }
            audit.status = DataPortabilityStatusEnum.completed
            audit.completed_at = _utc_now()
            audit.result_metadata = metadata

            payload["export_audit"] = {
                "request_id": audit.id,
                "requested_at": _iso(audit.requested_at),
                "completed_at": _iso(audit.completed_at),
                "format": audit.export_format,
                "include_documents": audit.include_documents,
                "result_metadata": metadata,
            }
            timestamp = _utc_now().strftime("%Y%m%d_%H%M%S")
            base_name = f"mis_datos_{timestamp}"
            json_bytes = _json_bytes(payload)

            if export_format == "json":
                export = DataPortabilityExport(
                    filename=f"{base_name}.json",
                    media_type="application/json",
                    content=json_bytes,
                )
            else:
                pdf_bytes = _render_portability_pdf(payload)

            if export_format == "pdf":
                export = DataPortabilityExport(
                    filename=f"{base_name}.pdf",
                    media_type="application/pdf",
                    content=pdf_bytes,
                )
            elif export_format == "zip":
                export = DataPortabilityExport(
                    filename=f"{base_name}.zip",
                    media_type="application/zip",
                    content=_build_zip_export(
                        payload=payload,
                        json_bytes=json_bytes,
                        pdf_bytes=pdf_bytes,
                        archive_files=archive_files,
                    ),
                )

            await self.repository.save_request(audit)
            return export
        except Exception as exc:
            audit.status = DataPortabilityStatusEnum.failed
            audit.completed_at = _utc_now()
            audit.error_message = str(exc)
            await self.repository.save_request(audit)
            raise

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
        documents = await self.repository.list_documents(user_id, internship_ids)
        presentation_letters = await self.repository.list_presentation_letters(user_id)
        self_evaluations = await self.repository.list_self_evaluations(user_id)
        supervisor_evaluations = await self.repository.list_supervisor_evaluations(
            internship_ids
        )

        document_payload = []
        archive_files: list[tuple[dict, Path]] = []
        for document in documents:
            export_path = (
                f"documentos/practica_{document.internship_id}/"
                f"{document.id}_{_safe_filename(document.file_name)}"
            )
            metadata = {
                "id": document.id,
                "internship_id": document.internship_id,
                "type": document.document_type.name if document.document_type else None,
                "source": (
                    "student"
                    if document.user_id == user_id
                    else "related_actor"
                ),
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
                archive_files.append((metadata, file_path))

        presentation_letter_payload = []
        for letter in presentation_letters:
            export_path = (
                "documentos_generados/cartas_presentacion/"
                f"{letter.id}_{_safe_filename(letter.generated_file_name)}"
            )
            metadata = {
                "id": letter.id,
                "practice_type": letter.practice_type,
                "file_name": letter.generated_file_name,
                "recipient_email": letter.recipient_email,
                "sent_at": _iso(letter.sent_at),
                "downloaded_at": _iso(letter.downloaded_at),
                "created_at": _iso(letter.created_at),
                "included_in_zip": False,
                "export_path": export_path if include_documents else None,
            }
            presentation_letter_payload.append(metadata)
            if include_documents:
                file_path = self._resolve_storage_path(
                    self.presentation_letter_storage_root,
                    letter.generated_file_path,
                    "Ruta de carta de presentación inválida",
                )
                metadata["included_in_zip"] = file_path.is_file()
                archive_files.append((metadata, file_path))

        payload = {
            "generated_at": _iso(_utc_now()),
            "profile": _user_payload(user),
            "internships": [_internship_payload(item) for item in internships],
            "status_history": [_history_payload(item) for item in history],
            "exceptions": [_exception_payload(item) for item in exceptions],
            "documents": document_payload,
            "presentation_letters": presentation_letter_payload,
            "self_evaluations": [
                _self_evaluation_payload(item) for item in self_evaluations
            ],
            "supervisor_evaluations": [
                _supervisor_evaluation_payload(item)
                for item in supervisor_evaluations
            ],
        }
        return payload, archive_files

    def _resolve_document_path(self, storage_key: str) -> Path:
        return self._resolve_storage_path(
            self.document_storage_root,
            storage_key,
            "Ruta documental inválida",
        )

    @staticmethod
    def _resolve_storage_path(
        storage_root: Path,
        storage_key: str,
        error_detail: str,
    ) -> Path:
        root = storage_root.resolve()
        file_path = (root / storage_key).resolve()
        if root != file_path and root not in file_path.parents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
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
        "address": internship.address,
        "city": internship.city,
        "org_phone": internship.org_phone,
        "web": internship.web,
        "supervisor_name": internship.supervisor_name,
        "supervisor_profession": internship.supervisor_profession,
        "supervisor_position": internship.supervisor_position,
        "supervisor_department": internship.supervisor_department,
        "supervisor_email": internship.supervisor_email,
        "supervisor_phone": internship.supervisor_phone,
        "start_date": _iso(internship.start_date),
        "end_date": _iso(internship.end_date),
        "schedule": internship.schedule,
        "days": internship.days,
        "modality": internship.modality,
        "internship_address": internship.internship_address,
        "activities": internship.act_description,
        "benefits": internship.ben_description,
        "amount": internship.amount,
        "internship_period": _enum_value(internship.internship_period),
        "internship_type": _enum_value(internship.internship_type),
        "has_school_insurance": internship.has_school_insurance,
        "insurance_status": _enum_value(internship.insurance_status),
        "insurance_validated_at": _iso(internship.insurance_validated_at),
        "insurance_notes": internship.insurance_notes,
        "status": internship.status.title if internship.status else None,
        "completion_status": _enum_value(internship.completion_status),
        "final_result": _enum_value(internship.final_result),
        "is_cancelled": internship.is_cancelled,
        "cancelled_at": _iso(internship.cancelled_at),
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


def _render_portability_pdf(payload: dict) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Resumen de datos del estudiante",
        author="Sistema de Gestión de Prácticas",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="PortabilityTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#202124"),
            alignment=TA_CENTER,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PortabilitySection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#9F204F"),
            spaceBefore=10,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PortabilitySubsection",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#343A40"),
            spaceBefore=8,
            spaceAfter=5,
        )
    )
    body_style = ParagraphStyle(
        name="PortabilityBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#343A40"),
    )
    muted_style = ParagraphStyle(
        name="PortabilityMuted",
        parent=body_style,
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#6C757D"),
    )
    story = [
        Paragraph("Resumen de datos del estudiante", styles["PortabilityTitle"]),
        Paragraph(
            "Copia legible de la información registrada en la plataforma.",
            muted_style,
        ),
        Spacer(1, 8),
    ]

    profile = payload["profile"]
    story.append(Paragraph("Datos personales y académicos", styles["PortabilitySection"]))
    story.append(
        _pdf_key_value_table(
            [
                ("Nombre", f"{profile.get('first_name', '')} {profile.get('last_name', '')}"),
                ("Correo", profile.get("email")),
                ("Matrícula", profile.get("enrollment")),
                ("RUT", profile.get("rut")),
                ("Carrera", profile.get("degree") or profile.get("cod_degree")),
                ("Año de ingreso", profile.get("admission_year")),
                ("Teléfono", profile.get("phone")),
                ("Generado", _format_pdf_date(payload.get("generated_at"))),
            ],
            body_style,
        )
    )

    internships = payload["internships"]
    story.append(Paragraph("Resumen de trayectoria", styles["PortabilitySection"]))
    if internships:
        rows = [["Tipo", "Organización", "Periodo", "Estado", "Resultado"]]
        rows.extend(
            [
                internship.get("internship_type"),
                internship.get("org_name"),
                internship.get("internship_period"),
                internship.get("status"),
                internship.get("final_result"),
            ]
            for internship in internships
        )
        story.append(
            _pdf_table(
                rows,
                [42 * mm, 45 * mm, 25 * mm, 28 * mm, 25 * mm],
                body_style,
                repeat_rows=1,
            )
        )
    else:
        story.append(Paragraph("No hay prácticas registradas.", body_style))

    histories = payload["status_history"]
    exceptions = payload["exceptions"]
    documents = payload["documents"]
    self_evaluations = payload["self_evaluations"]
    supervisor_evaluations = payload["supervisor_evaluations"]

    for index, internship in enumerate(internships):
        story.append(PageBreak())
        internship_id = internship["id"]
        story.append(
            Paragraph(
                f"{index + 1}. {_pdf_text(internship.get('internship_type'))}",
                styles["PortabilitySection"],
            )
        )
        story.append(
            _pdf_key_value_table(
                [
                    ("Organización", internship.get("org_name")),
                    ("Sector", internship.get("sector")),
                    (
                        "Dirección",
                        ", ".join(
                            filter(
                                None,
                                [internship.get("address"), internship.get("city")],
                            )
                        ),
                    ),
                    ("Periodo académico", internship.get("internship_period")),
                    (
                        "Fechas",
                        f"{_format_pdf_date(internship.get('start_date'))} a "
                        f"{_format_pdf_date(internship.get('end_date'))}",
                    ),
                    ("Modalidad", internship.get("modality")),
                    ("Estado", internship.get("status")),
                    ("Resultado final", internship.get("final_result")),
                    ("Supervisor", internship.get("supervisor_name")),
                    ("Correo supervisor", internship.get("supervisor_email")),
                ],
                body_style,
            )
        )
        story.append(Paragraph("Actividades y condiciones", styles["PortabilitySubsection"]))
        story.append(
            _pdf_key_value_table(
                [
                    ("Actividades", internship.get("activities")),
                    ("Beneficios", internship.get("benefits")),
                    ("Horario", internship.get("schedule")),
                    ("Días", internship.get("days")),
                    ("Seguro escolar", internship.get("insurance_status")),
                ],
                body_style,
            )
        )

        internship_history = [
            item for item in histories if item["internship_id"] == internship_id
        ]
        story.append(Paragraph("Historial de estados", styles["PortabilitySubsection"]))
        if internship_history:
            rows = [["Fecha", "Estado anterior", "Nuevo estado", "Motivo"]]
            rows.extend(
                [
                    _format_pdf_date(item.get("changed_at")),
                    item.get("previous_status"),
                    item.get("new_status"),
                    item.get("reason"),
                ]
                for item in internship_history
            )
            story.append(
                _pdf_table(
                    rows,
                    [28 * mm, 35 * mm, 35 * mm, 67 * mm],
                    body_style,
                    repeat_rows=1,
                )
            )
        else:
            story.append(Paragraph("Sin cambios de estado registrados.", muted_style))

        internship_documents = [
            item for item in documents if item["internship_id"] == internship_id
        ]
        story.append(Paragraph("Documentos relacionados", styles["PortabilitySubsection"]))
        if internship_documents:
            rows = [["Documento", "Tipo", "Estado", "Origen", "Observación"]]
            rows.extend(
                [
                    item.get("file_name"),
                    item.get("type"),
                    item.get("status"),
                    (
                        "Estudiante"
                        if item.get("source") == "student"
                        else "Actor relacionado"
                    ),
                    item.get("review_comment"),
                ]
                for item in internship_documents
            )
            story.append(
                _pdf_table(
                    rows,
                    [40 * mm, 30 * mm, 24 * mm, 28 * mm, 43 * mm],
                    body_style,
                    repeat_rows=1,
                )
            )
        else:
            story.append(Paragraph("Sin documentos relacionados.", muted_style))

        internship_exceptions = [
            item for item in exceptions if item["internship_id"] == internship_id
        ]
        if internship_exceptions:
            story.append(Paragraph("Excepciones", styles["PortabilitySubsection"]))
            rows = [["Regla", "Motivo", "Autorizada"]]
            rows.extend(
                [
                    item.get("rule"),
                    item.get("reason"),
                    _format_pdf_date(item.get("authorized_at")),
                ]
                for item in internship_exceptions
            )
            story.append(
                _pdf_table(
                    rows,
                    [35 * mm, 95 * mm, 35 * mm],
                    body_style,
                    repeat_rows=1,
                )
            )

        student_evaluations = [
            item
            for item in self_evaluations
            if item["internship_id"] == internship_id
        ]
        supervisor_items = [
            item
            for item in supervisor_evaluations
            if item["internship_id"] == internship_id
        ]
        if student_evaluations or supervisor_items:
            story.append(Paragraph("Evaluaciones", styles["PortabilitySubsection"]))
            evaluation_rows = [["Origen", "Estado", "Fecha", "Observaciones"]]
            evaluation_rows.extend(
                [
                    "Autoevaluación",
                    item.get("status"),
                    _format_pdf_date(item.get("submitted_at")),
                    item.get("observations"),
                ]
                for item in student_evaluations
            )
            evaluation_rows.extend(
                [
                    "Supervisor",
                    item.get("status"),
                    _format_pdf_date(item.get("submitted_at")),
                    item.get("observations"),
                ]
                for item in supervisor_items
            )
            story.append(
                _pdf_table(
                    evaluation_rows,
                    [30 * mm, 28 * mm, 32 * mm, 75 * mm],
                    body_style,
                    repeat_rows=1,
                )
            )

    story.append(PageBreak())
    story.append(Paragraph("Índice de archivos", styles["PortabilitySection"]))
    file_rows = [["Archivo", "Categoría", "Práctica", "Incluido"]]
    file_rows.extend(
        [
            item.get("file_name"),
            item.get("type"),
            item.get("internship_id"),
            "Sí" if item.get("included_in_zip") else "No",
        ]
        for item in documents
    )
    file_rows.extend(
        [
            item.get("file_name"),
            "Carta de presentación",
            item.get("practice_type"),
            "Sí" if item.get("included_in_zip") else "No",
        ]
        for item in payload["presentation_letters"]
    )
    if len(file_rows) == 1:
        story.append(Paragraph("No hay archivos asociados.", body_style))
    else:
        story.append(
            _pdf_table(
                file_rows,
                [65 * mm, 40 * mm, 30 * mm, 20 * mm],
                body_style,
                repeat_rows=1,
            )
        )

    document.build(
        story,
        onFirstPage=_draw_pdf_footer,
        onLaterPages=_draw_pdf_footer,
    )
    return buffer.getvalue()


def _pdf_key_value_table(rows: list[tuple[str, object]], body_style) -> Table:
    formatted_rows = [
        [
            Paragraph(f"<b>{escape(label)}</b>", body_style),
            Paragraph(_pdf_text(value), body_style),
        ]
        for label, value in rows
    ]
    table = Table(formatted_rows, colWidths=[48 * mm, 117 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F4F5F7")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#DADCE0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _pdf_table(
    rows: list[list[object]],
    col_widths: list[float],
    body_style,
    *,
    repeat_rows: int = 0,
) -> Table:
    formatted_rows = [
        [Paragraph(_pdf_text(value), body_style) for value in row]
        for row in rows
    ]
    table = Table(
        formatted_rows,
        colWidths=col_widths,
        repeatRows=repeat_rows,
        hAlign="LEFT",
    )
    style_commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#DADCE0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if repeat_rows:
        style_commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, repeat_rows - 1), colors.HexColor("#F4F5F7")),
                ("TEXTCOLOR", (0, 0), (-1, repeat_rows - 1), colors.HexColor("#202124")),
            ]
        )
    table.setStyle(TableStyle(style_commands))
    return table


def _draw_pdf_footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#6C757D"))
    canvas.drawString(18 * mm, 10 * mm, "Sistema de Gestión de Prácticas")
    canvas.drawRightString(
        A4[0] - 18 * mm,
        10 * mm,
        f"Página {document.page}",
    )
    canvas.restoreState()


def _build_zip_export(
    *,
    payload: dict,
    json_bytes: bytes,
    pdf_bytes: bytes,
    archive_files: list[tuple[dict, Path]],
) -> bytes:
    readme_bytes = _portability_readme().encode("utf-8")
    manifest_files = [
        _manifest_bytes_entry("datos/data.json", "structured_data", json_bytes),
        _manifest_bytes_entry(
            "resumen_estudiante.pdf",
            "human_readable_report",
            pdf_bytes,
        ),
        _manifest_bytes_entry("LEEME.txt", "instructions", readme_bytes),
    ]
    included_archive_files = []
    missing_files = []
    for metadata, file_path in archive_files:
        if file_path.is_file():
            manifest_files.append(
                {
                    "path": metadata["export_path"],
                    "category": (
                        "generated_document"
                        if metadata["export_path"].startswith("documentos_generados/")
                        else "related_document"
                    ),
                    "size_bytes": file_path.stat().st_size,
                    "sha256": _file_sha256(file_path),
                    "related_internship_id": metadata.get("internship_id"),
                }
            )
            included_archive_files.append((metadata, file_path))
        else:
            missing_files.append(
                {
                    "path": metadata.get("export_path"),
                    "file_name": metadata.get("file_name"),
                }
            )

    manifest = {
        "schema_version": "1.0",
        "generated_at": payload["generated_at"],
        "export_request_id": payload["export_audit"]["request_id"],
        "files": manifest_files,
        "missing_files": missing_files,
    }
    manifest_bytes = _json_bytes(manifest)

    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("datos/data.json", json_bytes)
        archive.writestr("resumen_estudiante.pdf", pdf_bytes)
        archive.writestr("manifest.json", manifest_bytes)
        archive.writestr("LEEME.txt", readme_bytes)
        for metadata, file_path in included_archive_files:
            archive.write(file_path, metadata["export_path"])
    return buffer.getvalue()


def _manifest_bytes_entry(path: str, category: str, content: bytes) -> dict:
    return {
        "path": path,
        "category": category,
        "size_bytes": len(content),
        "sha256": sha256(content).hexdigest(),
        "related_internship_id": None,
    }


def _file_sha256(file_path: Path) -> str:
    digest = sha256()
    with file_path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_filename(filename: str) -> str:
    basename = Path(filename).name
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", basename).strip(" .")
    return sanitized or "archivo"


def _pdf_text(value: object) -> str:
    if value is None or value == "":
        return "No registrado"
    if isinstance(value, bool):
        return "Sí" if value else "No"
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, str):
        value = PDF_VALUE_LABELS.get(value, value)
    return escape(str(value)).replace("\n", "<br/>")


def _format_pdf_date(value: object) -> str:
    if not value:
        return "No registrado"
    raw_value = str(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_value):
        return date.fromisoformat(raw_value).strftime("%d-%m-%Y")
    try:
        normalized = raw_value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed.strftime("%d-%m-%Y %H:%M")
    except ValueError:
        return raw_value


def _portability_readme() -> str:
    return (
        "PAQUETE DE DATOS DEL ESTUDIANTE\n"
        "================================\n\n"
        "resumen_estudiante.pdf: informe legible para revisión personal.\n"
        "datos/data.json: copia estructurada de los datos exportados.\n"
        "manifest.json: listado de archivos, tamaños y checksums SHA-256.\n"
        "documentos/: archivos asociados a las prácticas del estudiante.\n"
        "documentos_generados/: archivos producidos por la plataforma.\n\n"
        "Este paquete puede contener información personal y antecedentes "
        "reservados. Guárdalo en un lugar seguro.\n"
    )


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
