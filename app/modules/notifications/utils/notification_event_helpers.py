"""Helpers de construccion de notificaciones para eventos del sistema.

Este modulo define funciones de conveniencia para crear notificaciones
a partir de eventos administrativos como aprobacion, rechazo, derivacion
de practicas y cambios de estado de requisitos. Cada helper construye
el asunto, contenido y payload minimos correspondientes al tipo de evento.
"""

from datetime import UTC, datetime
from html import escape

from app.modules.notifications.models.notification_model import (
    Notification,
    NotificationEventTypeEnum,
    NotificationStatusEnum,
)


BRAND_PRIMARY = "#d22864"
BRAND_DARK = "#8B1D46"
BRAND_PURPLE = "#972fa4"
BACKGROUND = "#f8f9fa"
PANEL_BACKGROUND = "#fff0f6"
PANEL_BORDER = "#ffdeeb"
TEXT_PRIMARY = "#111827"
TEXT_SECONDARY = "#4b5563"


def _build_email_body(
    title: str,
    intro: str,
    details: list[tuple[str, str | int | None]],
    action_label: str = "Ingresar a la plataforma",
    action_url: str | None = None,
    footer_note: str | None = None,
) -> str:
    """Construye el HTML transaccional compartido para notificaciones."""

    detail_rows = "".join(
        _build_detail_row(label, value)
        for label, value in details
        if value is not None and str(value).strip()
    )
    safe_title = escape(title)
    safe_intro = escape(intro)
    safe_action_label = escape(action_label)
    safe_action_url = escape(action_url, quote=True) if action_url else None
    note = footer_note or (
        "Este es un mensaje automático del Sistema de Gestión de Prácticas FICA."
    )
    safe_note = escape(note)
    action_html = (
        f'<a href="{safe_action_url}" '
        f'style="display:inline-block;background:{BRAND_PRIMARY};color:#ffffff;'
        "text-decoration:none;padding:14px 22px;border-radius:12px;"
        f'font-weight:700;font-size:15px;">{safe_action_label}</a>'
        if safe_action_url
        else (
            f'<span style="display:inline-block;background:{BRAND_PRIMARY};'
            "color:#ffffff;text-decoration:none;padding:14px 22px;"
            f'border-radius:12px;font-weight:700;font-size:15px;">{safe_action_label}</span>'
        )
    )

    return f"""
<!doctype html>
<html lang="es">
  <body style="margin:0;padding:0;background:{BACKGROUND};font-family:Inter,Arial,sans-serif;color:{TEXT_PRIMARY};">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:{BACKGROUND};padding:24px 0;">
      <tr>
        <td align="center" style="padding:0 16px;">
          <table role="presentation" width="640" cellspacing="0" cellpadding="0" style="width:100%;max-width:640px;background:#ffffff;border-radius:20px;overflow:hidden;border:1px solid #e5e7eb;box-shadow:0 10px 32px rgba(17,24,39,.08);">
            <tr>
              <td style="background:{BRAND_PRIMARY};padding:24px 32px;color:#ffffff;">
                <div style="font-size:24px;font-weight:700;line-height:1.2;">Sistema de Gestión de Prácticas</div>
                <div style="font-size:14px;line-height:1.5;opacity:.92;margin-top:4px;">Facultad de Ingeniería y Ciencias</div>
              </td>
            </tr>
            <tr>
              <td style="padding:32px;">
                <h1 style="margin:0 0 16px;font-size:28px;line-height:1.2;color:{BRAND_DARK};font-weight:800;">{safe_title}</h1>
                <p style="margin:0 0 24px;font-size:16px;line-height:1.65;color:{TEXT_SECONDARY};">{safe_intro}</p>
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:{PANEL_BACKGROUND};border:1px solid {PANEL_BORDER};border-radius:16px;margin:0 0 24px;">
                  <tr>
                    <td style="padding:20px;">
                      {detail_rows}
                    </td>
                  </tr>
                </table>
                <p style="margin:0 0 24px;font-size:15px;line-height:1.6;color:{TEXT_SECONDARY};">Ingresa a la plataforma para revisar el detalle actualizado y continuar con el proceso si corresponde.</p>
                {action_html}
              </td>
            </tr>
            <tr>
              <td style="background:linear-gradient(90deg,{BRAND_PRIMARY} 0%,{BRAND_PURPLE} 100%);padding:18px 32px;color:#ffffff;font-size:13px;line-height:1.5;">
                {safe_note}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
""".strip()


def _build_detail_row(label: str, value: str | int | None) -> str:
    safe_label = escape(label)
    safe_value = escape(str(value))

    return f"""
<div style="margin:0 0 16px;">
  <p style="margin:0 0 6px;font-size:13px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:.02em;">{safe_label}</p>
  <p style="margin:0;font-size:16px;line-height:1.5;color:{TEXT_PRIMARY};font-weight:700;">{safe_value}</p>
</div>
""".strip()


def _format_internship_request_type(internship_type: object | None) -> str:
    raw_value = getattr(internship_type, "value", internship_type)
    if raw_value is None:
        return "práctica"

    normalized = str(raw_value).strip()
    display_by_type = {
        "Práctica de Estudio I": "práctica I",
        "Práctica de Estudio II": "práctica II",
        "Práctica Controlada": "práctica controlada",
        "Tesis": "tesis",
    }
    return display_by_type.get(normalized, normalized.lower())


def build_dirae_document_package_email_notification(
    *,
    recipient_email: str,
    actor_email: str | None,
    internship_ids: list[int],
    filenames: list[str],
    attachments: list[dict[str, str]],
    message: str | None = None,
) -> Notification:
    """Construye una notificacion externa con adjuntos DIRAE."""

    package_count = len(internship_ids)
    package_label = (
        f"{package_count} expediente"
        if package_count == 1
        else f"{package_count} expedientes"
    )
    extra_message = message.strip() if message else None
    details: list[tuple[str, str | int | None]] = [
        ("Destinatario DIRAE", recipient_email),
        ("Enviado por", actor_email),
        ("Expedientes incluidos", package_label),
        ("IDs de práctica", ", ".join(str(item) for item in internship_ids)),
        ("Archivos adjuntos", ", ".join(filenames)),
        ("Mensaje de Secretaría", extra_message),
    ]

    return Notification(
        recipient_user_id=None,
        recipient_email=recipient_email,
        event_type=NotificationEventTypeEnum.custom,
        subject="Expediente documental DIRAE generado desde Gestión de Prácticas",
        content=_build_email_body(
            title="Expediente documental para DIRAE",
            intro=(
                "Secretaría de Carrera generó y envió el expediente documental "
                "para revisión DIRAE. El PDF del expediente se adjunta a este correo."
            ),
            details=details,
            action_label="Correo informativo",
            footer_note=(
                "Este mensaje fue generado desde el Sistema de Gestión de "
                "Prácticas FICA. No respondas directamente a este correo automático."
            ),
        ),
        status=NotificationStatusEnum.simulated,
        payload={
            "event": "dirae_document_package_email",
            "recipient_email": recipient_email,
            "actor_email": actor_email,
            "internship_ids": internship_ids,
            "filenames": filenames,
            "attachments": attachments,
        },
    )


def build_internship_approved_notification(
    recipient_user_id: int,
    recipient_email: str | None,
    internship_id: int,
    org_name: str,
    internship_type: object | None = None,
    status: NotificationStatusEnum = NotificationStatusEnum.simulated,
) -> Notification:
    """Construye una notificacion para el evento de aprobacion de solicitud.

    Args:
        recipient_user_id: Identificador del usuario destinatario.
        recipient_email: Correo electronico del destinatario (opcional).
        internship_id: Identificador de la solicitud aprobada.
        org_name: Nombre de la organizacion de la practica.
        internship_type: Tipo de solicitud de practica aprobada.
        status: Estado inicial de la notificacion (por defecto simulated).

    Returns:
        Entidad `Notification` lista para ser persistida.
    """

    request_type = _format_internship_request_type(internship_type)

    return Notification(
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        event_type=NotificationEventTypeEnum.internship_approved,
        subject="Solicitud de práctica aprobada",
        content=_build_email_body(
            title="Solicitud de práctica aprobada",
            intro=(
                f"Su solicitud de {request_type} ha sido aprobada por administración. "
                "Revise el detalle del proceso en la plataforma."
            ),
            details=[
                ("Organización", org_name),
                ("Estado", "Aprobada"),
                ("N° de solicitud", f"#{internship_id}"),
            ],
            action_label="Ver mi solicitud",
        ),
        status=status,
        payload={"internship_id": internship_id},
    )


def build_appointment_scheduled_notification(
    recipient_user_id: int,
    recipient_email: str | None,
    scheduling_request_id: int | None,
    presentation_id: int | None,
    scheduled_date: str | None,
    scheduled_time: str | None,
    modality: str | None = None,
    location: str | None = None,
    resolved_by_role: str | None = None,
    status: NotificationStatusEnum = NotificationStatusEnum.simulated,
) -> Notification:
    """Construye una notificacion para el evento de cita agendada.

    Args:
        recipient_user_id: Identificador del estudiante destinatario.
        recipient_email: Correo electronico del estudiante (opcional).
        scheduling_request_id: Identificador de la solicitud respondida (opcional).
        presentation_id: Identificador de la cita (Presentation) creada.
        scheduled_date: Fecha asignada (isoformat) de la cita.
        scheduled_time: Rango horario asignado (texto legible).
        modality: Modalidad de la cita (Presencial/Remoto/Híbrido).
        location: Ubicación o enlace de la reunión.
        resolved_by_role: Rol de visualización de quien agendó
            (Director/Coordinador).
        status: Estado inicial de la notificacion (por defecto simulated).

    Returns:
        Entidad `Notification` lista para ser persistida.
    """

    agendador_label = resolved_by_role or "Coordinación"

    details = [
        ("Fecha", scheduled_date),
        ("Hora", scheduled_time),
        ("Modalidad", modality),
        ("Ubicación", location),
        ("Agendado por", agendador_label),
    ]

    if scheduling_request_id is not None:
        details.append(("N° de solicitud", f"#{scheduling_request_id}"))

    intro_text = (
        "Tienes una cita confirmada para la presentación final de tu práctica. "
        "Revisa el detalle en la plataforma para asistir a tiempo."
        if scheduling_request_id is None
        else (
            "Tu solicitud de agendamiento fue respondida y tienes una cita "
            "confirmada. Revisa el detalle en la plataforma para asistir a "
            "tiempo."
        )
    )

    return Notification(
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        event_type=NotificationEventTypeEnum.appointment_scheduled,
        subject="Cita agendada",
        content=_build_email_body(
            title="Cita agendada",
            intro=intro_text,
            details=details,
            action_label="Ver mis citas",
        ),
        status=status,
        payload={
            "scheduling_request_id": scheduling_request_id,
            "presentation_id": presentation_id,
            "scheduled_date": scheduled_date,
            "scheduled_time": scheduled_time,
            "resolved_by_role": resolved_by_role,
        },
    )


def build_internship_rejected_notification(
    recipient_user_id: int,
    recipient_email: str | None,
    internship_id: int,
    org_name: str,
    reason: str | None = None,
    status: NotificationStatusEnum = NotificationStatusEnum.simulated,
) -> Notification:
    """Construye una notificacion para el evento de rechazo de solicitud.

    Args:
        recipient_user_id: Identificador del usuario destinatario.
        recipient_email: Correo electronico del destinatario (opcional).
        internship_id: Identificador de la solicitud rechazada.
        org_name: Nombre de la organizacion de la practica.
        reason: Motivo del rechazo proporcionado por el actor.
        status: Estado inicial de la notificacion (por defecto simulated).

    Returns:
        Entidad `Notification` lista para ser persistida.
    """

    return Notification(
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        event_type=NotificationEventTypeEnum.internship_rejected,
        subject="Solicitud de práctica rechazada",
        content=_build_email_body(
            title="Solicitud de práctica rechazada",
            intro=(
                "Su solicitud de práctica fue rechazada durante la revisión "
                "administrativa. Revise la información asociada para conocer "
                "los pasos a seguir."
            ),
            details=[
                ("Organización", org_name),
                ("Estado", "Rechazada"),
                ("N° de solicitud", f"#{internship_id}"),
                ("Motivo", reason),
            ],
            action_label="Revisar solicitud",
        ),
        status=status,
        payload={"internship_id": internship_id, "reason": reason},
    )


def build_internship_derived_notification(
    recipient_user_id: int,
    recipient_email: str | None,
    internship_id: int,
    org_name: str,
    reason: str | None = None,
    status: NotificationStatusEnum = NotificationStatusEnum.simulated,
) -> Notification:
    """Construye una notificacion para el evento de derivacion de expediente DIRAE.

    Args:
        recipient_user_id: Identificador del usuario destinatario.
        recipient_email: Correo electronico del destinatario (opcional).
        internship_id: Identificador de la practica asociada al expediente.
        org_name: Nombre de la organizacion de la practica.
        reason: Motivo de la derivacion proporcionado por el actor.
        status: Estado inicial de la notificacion (por defecto simulated).

    Returns:
        Entidad `Notification` lista para ser persistida.
    """

    return Notification(
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        event_type=NotificationEventTypeEnum.internship_derived,
        subject="Expediente DIRAE de práctica derivado",
        content=_build_email_body(
            title="Expediente DIRAE de práctica derivado",
            intro=(
                "El expediente DIRAE asociado a su práctica fue derivado para una revisión adicional. "
                "Le notificaremos cuando exista una nueva actualización."
            ),
            details=[
                ("Organización", org_name),
                ("Estado DIRAE", "En revisión"),
                ("N° de práctica", f"#{internship_id}"),
                ("Motivo", reason),
            ],
            action_label="Ver expediente DIRAE",
        ),
        status=status,
        payload={"internship_id": internship_id, "reason": reason},
    )


def build_internship_created_notification(
    recipient_user_id: int,
    recipient_email: str | None,
    internship_id: int,
    org_name: str,
    student_user_id: int,
    status: NotificationStatusEnum = NotificationStatusEnum.simulated,
) -> Notification:
    """Construye una notificacion para revisores tras crear una solicitud."""

    return Notification(
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        event_type=NotificationEventTypeEnum.custom,
        subject="Nueva solicitud de práctica registrada",
        content=_build_email_body(
            title="Nueva solicitud de práctica registrada",
            intro=(
                "Se registró una nueva solicitud de práctica pendiente de revisión "
                "administrativa. Puede revisarla desde el panel de coordinación."
            ),
            details=[
                ("Organización", org_name),
                ("Estado", "Pendiente de revisión"),
                ("N° de solicitud", f"#{internship_id}"),
                ("ID estudiante", student_user_id),
            ],
            action_label="Revisar solicitud",
        ),
        status=status,
        payload={
            "event": "internship_created",
            "internship_id": internship_id,
            "student_user_id": student_user_id,
        },
    )


def build_document_uploaded_notification(
    recipient_user_id: int,
    recipient_email: str | None,
    document_id: int,
    internship_id: int,
    document_type: str,
    file_name: str,
    org_name: str,
    status: NotificationStatusEnum = NotificationStatusEnum.simulated,
) -> Notification:
    """Construye una notificacion para revisores tras cargar un documento."""

    return Notification(
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        event_type=NotificationEventTypeEnum.custom,
        subject="Nuevo documento cargado",
        content=_build_email_body(
            title="Nuevo documento cargado",
            intro=(
                "Un estudiante cargó un nuevo documento asociado a una práctica. "
                "Revise el archivo para continuar el proceso documental."
            ),
            details=[
                ("Organización", org_name),
                ("Documento", document_type),
                ("Archivo", file_name),
                ("N° de práctica", f"#{internship_id}"),
                ("ID documento", document_id),
            ],
            action_label="Revisar documento",
        ),
        status=status,
        payload={
            "event": "document_uploaded",
            "document_id": document_id,
            "internship_id": internship_id,
            "document_type": document_type,
        },
    )


def build_document_status_changed_notification(
    recipient_user_id: int,
    recipient_email: str | None,
    document_id: int,
    internship_id: int,
    document_type: str,
    new_status: str,
    comment: str | None = None,
    status: NotificationStatusEnum = NotificationStatusEnum.simulated,
) -> Notification:
    """Construye una notificacion para cambios de estado documental."""

    status_label = "aprobado" if new_status == "approved" else "observado"
    status_display = "Aprobado" if new_status == "approved" else "Observado"

    return Notification(
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        event_type=NotificationEventTypeEnum.custom,
        subject=f"Documento {status_label}: {document_type}",
        content=_build_email_body(
            title=f"Documento {status_label}",
            intro=(
                f"Su documento fue {status_label} durante la revisión "
                "administrativa. Revise el detalle actualizado en la plataforma."
            ),
            details=[
                ("Documento", document_type),
                ("Estado", status_display),
                ("N° de práctica", f"#{internship_id}"),
                ("ID documento", document_id),
                ("Observación", comment),
            ],
            action_label="Ver documento",
        ),
        status=status,
        payload={
            "event": "document_status_changed",
            "document_id": document_id,
            "internship_id": internship_id,
            "document_type": document_type,
            "new_status": new_status,
            "comment": comment,
        },
    )


def build_supervisor_evaluation_invitation_notification(
    recipient_email: str | None,
    internship_id: int,
    org_name: str,
    student_name: str,
    supervisor_name: str | None,
    internship_type: object | None,
    invitation_url: str,
    expires_at: datetime,
    status: NotificationStatusEnum = NotificationStatusEnum.simulated,
) -> Notification:
    """Construye la invitacion publica para evaluacion de supervisor."""

    request_type = _format_internship_request_type(internship_type)

    return Notification(
        recipient_user_id=None,
        recipient_email=recipient_email,
        event_type=NotificationEventTypeEnum.custom,
        subject="Evaluación de práctica pendiente",
        content=_build_email_body(
            title="Evaluación de práctica pendiente",
            intro=(
                f"Se solicitó su evaluación como supervisor/a de {request_type}. "
                "Use el enlace para completar el formulario público de evaluación."
            ),
            details=[
                ("Estudiante", student_name),
                ("Supervisor/a", supervisor_name),
                ("Organización", org_name),
                ("Tipo de práctica", request_type.capitalize()),
                ("N° de práctica", f"#{internship_id}"),
                ("Vencimiento", expires_at.strftime("%Y-%m-%d %H:%M")),
            ],
            action_label="Evaluar práctica",
            action_url=invitation_url,
            footer_note=(
                "Este enlace es personal y de un solo uso. Si usted no reconoce "
                "esta solicitud, contacte al equipo administrativo."
            ),
        ),
        status=status,
        payload={
            "internship_id": internship_id,
            "event": "supervisor_evaluation_invitation",
            "expires_at": expires_at.isoformat(),
        },
    )


def build_self_evaluation_submitted_notification(
    recipient_user_id: int,
    recipient_email: str | None,
    internship_id: int,
    org_name: str,
    self_evaluation_id: int,
    status: NotificationStatusEnum = NotificationStatusEnum.simulated,
) -> Notification:
    """Construye la confirmacion al estudiante por autoevaluacion enviada."""

    return Notification(
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        event_type=NotificationEventTypeEnum.custom,
        subject="Autoevaluación enviada",
        content=_build_email_body(
            title="Autoevaluación enviada",
            intro=(
                "Tu autoevaluación de práctica fue registrada correctamente. "
                "El proceso continuará con la revisión correspondiente."
            ),
            details=[
                ("Organización", org_name),
                ("N° de práctica", f"#{internship_id}"),
                ("ID autoevaluación", self_evaluation_id),
            ],
            action_label="Ver seguimiento",
        ),
        status=status,
        payload={
            "event": "self_evaluation_submitted",
            "internship_id": internship_id,
            "self_evaluation_id": self_evaluation_id,
        },
    )


def build_self_evaluation_submitted_admin_notification(
    recipient_user_id: int,
    recipient_email: str | None,
    internship_id: int,
    org_name: str,
    student_user_id: int,
    self_evaluation_id: int,
    status: NotificationStatusEnum = NotificationStatusEnum.simulated,
) -> Notification:
    """Construye aviso administrativo por autoevaluacion enviada."""

    return Notification(
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        event_type=NotificationEventTypeEnum.custom,
        subject="Autoevaluación de estudiante enviada",
        content=_build_email_body(
            title="Autoevaluación de estudiante enviada",
            intro=(
                "Un estudiante envió su autoevaluación de práctica. Revise el "
                "avance del proceso desde el panel administrativo."
            ),
            details=[
                ("Organización", org_name),
                ("N° de práctica", f"#{internship_id}"),
                ("ID estudiante", student_user_id),
                ("ID autoevaluación", self_evaluation_id),
            ],
            action_label="Revisar proceso",
        ),
        status=status,
        payload={
            "event": "self_evaluation_submitted_admin",
            "internship_id": internship_id,
            "self_evaluation_id": self_evaluation_id,
            "student_id": student_user_id,
        },
    )


def build_user_activation_notification(
    recipient_user_id: int,
    recipient_email: str,
    activation_url: str,
    expires_at: datetime,
    status: NotificationStatusEnum = NotificationStatusEnum.simulated,
) -> Notification:
    """Construye una notificacion de activacion para usuarios creados por Superadmin."""

    return Notification(
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        event_type=NotificationEventTypeEnum.custom,
        subject="Cuenta creada en Sistema de Gestión de Prácticas",
        content=_build_email_body(
            title="Cuenta creada",
            intro=(
                "Se creó una cuenta para usted en el Sistema de Gestión de "
                "Prácticas. Use el enlace de activación para definir su "
                "contraseña definitiva."
            ),
            details=[
                ("Usuario", recipient_email),
                ("Acción requerida", "Definir contraseña inicial"),
                ("Vencimiento", expires_at.strftime("%Y-%m-%d %H:%M")),
            ],
            action_label="Activar cuenta",
            action_url=activation_url,
            footer_note=(
                "Este enlace es de un solo uso. Si usted no solicitó o no esperaba "
                "esta cuenta, contacte al equipo administrativo."
            ),
        ),
        status=status,
        payload={
            "event": "user_account_activation_created",
            "recipient_user_id": recipient_user_id,
            "expires_at": expires_at.isoformat(),
        },
    )


def build_user_temporary_credentials_notification(
    recipient_user_id: int,
    recipient_email: str,
    temporary_password: str,
    status: NotificationStatusEnum = NotificationStatusEnum.simulated,
) -> Notification:
    """Compatibilidad: ya no debe usarse para altas nuevas por Superadmin."""

    return build_user_activation_notification(
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        activation_url="",
        expires_at=datetime.now(UTC).replace(tzinfo=None),
        status=status,
    )


def build_requirement_status_changed_notification(
    recipient_user_id: int,
    recipient_email: str | None,
    requirement_id: int,
    requirement_type: str,
    new_status: str,
    previous_status: str | None = None,
    status: NotificationStatusEnum = NotificationStatusEnum.simulated,
) -> Notification:
    """Construye una notificacion para el evento de cambio de estado de requisito.

    Args:
        recipient_user_id: Identificador del usuario destinatario.
        recipient_email: Correo electronico del destinatario (opcional).
        requirement_id: Identificador del requisito actualizado.
        requirement_type: Tipo/nombre del requisito.
        new_status: Nuevo estado asignado al requisito.
        previous_status: Estado anterior del requisito (opcional).
        status: Estado inicial de la notificacion (por defecto simulated).

    Returns:
        Entidad `Notification` lista para ser persistida.
    """

    return Notification(
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        event_type=NotificationEventTypeEnum.requirement_status_changed,
        subject=f"Requisito actualizado: {requirement_type}",
        content=_build_email_body(
            title=f"Requisito actualizado: {requirement_type}",
            intro=(
                "Uno de sus requisitos de práctica fue actualizado por el "
                "equipo administrativo. Revise el nuevo estado en la plataforma."
            ),
            details=[
                ("Requisito", requirement_type),
                ("Estado nuevo", new_status),
                ("Estado anterior", previous_status),
                ("ID requisito", requirement_id),
            ],
            action_label="Revisar requisito",
        ),
        status=status,
        payload={
            "requirement_id": requirement_id,
            "requirement_type": requirement_type,
            "new_status": new_status,
            "previous_status": previous_status,
        },
    )


def build_presentation_approved_notification(
    recipient_user_id: int,
    recipient_email: str | None,
    internship_id: int,
    internship_type: object | None = None,
    evaluator_role: str | None = None,
    status: NotificationStatusEnum = NotificationStatusEnum.simulated,
) -> Notification:
    """Construye una notificacion para el evento de aprobacion de presentacion final.

    Args:
        recipient_user_id: Identificador del estudiante destinatario.
        recipient_email: Correo electronico del estudiante (opcional).
        internship_id: Identificador de la practica.
        internship_type: Tipo de practica.
        evaluator_role: Rol de quien aprobo (Coordinador o Director).
        status: Estado inicial de la notificacion.

    Returns:
        Entidad `Notification` lista para ser persistida.
    """

    request_type = _format_internship_request_type(internship_type)
    role_label = evaluator_role or "Coordinación"

    return Notification(
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        event_type=NotificationEventTypeEnum.presentation_approved,
        subject="Presentación final aprobada",
        content=_build_email_body(
            title="Presentación final aprobada",
            intro=(
                f"Felicidades, tu presentación final de {request_type} ha sido aprobada "
                f"por el/la {role_label.lower()} de prácticas. Tu proceso se encuentra en etapa de finalización."
            ),
            details=[
                ("Tipo de Práctica", request_type.capitalize()),
                ("Resultado de Presentación", "Aprobada"),
                ("Calificado por", role_label),
            ],
            action_label="Ver seguimiento",
        ),
        status=status,
        payload={
            "internship_id": internship_id,
            "evaluator_role": evaluator_role,
        },
    )
