"""Helpers de construccion de notificaciones para eventos del sistema.

Este modulo define funciones de conveniencia para crear notificaciones
a partir de eventos administrativos como aprobacion, rechazo, derivacion
de practicas y cambios de estado de requisitos. Cada helper construye
el asunto, contenido y payload minimos correspondientes al tipo de evento.
"""

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
    note = footer_note or (
        "Este es un mensaje automático del Sistema de Gestión de Prácticas FICA."
    )
    safe_note = escape(note)

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
                <span style="display:inline-block;background:{BRAND_PRIMARY};color:#ffffff;text-decoration:none;padding:14px 22px;border-radius:12px;font-weight:700;font-size:15px;">{safe_action_label}</span>
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


def build_internship_approved_notification(
    recipient_user_id: int,
    recipient_email: str | None,
    internship_id: int,
    org_name: str,
    status: NotificationStatusEnum = NotificationStatusEnum.simulated,
) -> Notification:
    """Construye una notificacion para el evento de aprobacion de practica.

    Args:
        recipient_user_id: Identificador del usuario destinatario.
        recipient_email: Correo electronico del destinatario (opcional).
        internship_id: Identificador de la practica aprobada.
        org_name: Nombre de la organizacion de la practica.
        status: Estado inicial de la notificacion (por defecto simulated).

    Returns:
        Entidad `Notification` lista para ser persistida.
    """

    return Notification(
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        event_type=NotificationEventTypeEnum.internship_approved,
        subject="Práctica aprobada",
        content=_build_email_body(
            title="Práctica aprobada",
            intro=(
                "Su práctica ha sido aprobada por el equipo administrativo. "
                "Revise el detalle del proceso en la plataforma."
            ),
            details=[
                ("Organización", org_name),
                ("Estado", "Aprobada"),
                ("N° de práctica", f"#{internship_id}"),
            ],
            action_label="Ver mi práctica",
        ),
        status=status,
        payload={"internship_id": internship_id},
    )


def build_internship_rejected_notification(
    recipient_user_id: int,
    recipient_email: str | None,
    internship_id: int,
    org_name: str,
    reason: str | None = None,
    status: NotificationStatusEnum = NotificationStatusEnum.simulated,
) -> Notification:
    """Construye una notificacion para el evento de rechazo de practica.

    Args:
        recipient_user_id: Identificador del usuario destinatario.
        recipient_email: Correo electronico del destinatario (opcional).
        internship_id: Identificador de la practica rechazada.
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
        subject="Práctica rechazada",
        content=_build_email_body(
            title="Práctica rechazada",
            intro=(
                "Su solicitud de práctica fue rechazada durante la revisión "
                "administrativa. Revise la información asociada para conocer "
                "los pasos a seguir."
            ),
            details=[
                ("Organización", org_name),
                ("Estado", "Rechazada"),
                ("N° de práctica", f"#{internship_id}"),
                ("Motivo", reason),
            ],
            action_label="Revisar práctica",
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
    """Construye una notificacion para el evento de derivacion de practica a DIRAE.

    Args:
        recipient_user_id: Identificador del usuario destinatario.
        recipient_email: Correo electronico del destinatario (opcional).
        internship_id: Identificador de la practica derivada.
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
        subject="Práctica derivada a DIRAE",
        content=_build_email_body(
            title="Práctica derivada a DIRAE",
            intro=(
                "Su práctica fue derivada a DIRAE para una revisión adicional. "
                "Le notificaremos cuando exista una nueva actualización."
            ),
            details=[
                ("Organización", org_name),
                ("Estado", "Derivada a DIRAE"),
                ("N° de práctica", f"#{internship_id}"),
                ("Motivo", reason),
            ],
            action_label="Ver estado de práctica",
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
    """Construye una notificacion para revisores tras crear una practica."""

    return Notification(
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        event_type=NotificationEventTypeEnum.custom,
        subject="Nueva práctica registrada",
        content=_build_email_body(
            title="Nueva práctica registrada",
            intro=(
                "Se registró una nueva práctica pendiente de revisión "
                "administrativa. Puede revisarla desde el panel de coordinación."
            ),
            details=[
                ("Organización", org_name),
                ("Estado", "Pendiente de revisión"),
                ("N° de práctica", f"#{internship_id}"),
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
