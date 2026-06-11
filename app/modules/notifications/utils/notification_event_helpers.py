"""Helpers de construccion de notificaciones para eventos del sistema.

Este modulo define funciones de conveniencia para crear notificaciones
a partir de eventos administrativos como aprobacion, rechazo, derivacion
de practicas y cambios de estado de requisitos. Cada helper construye
el asunto, contenido y payload minimos correspondientes al tipo de evento.
"""

from app.modules.notifications.models.notification_model import (
    Notification,
    NotificationEventTypeEnum,
    NotificationStatusEnum,
)


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
        content=(
            f"Su práctica en <strong>{org_name}</strong> ha sido "
            f"<strong>aprobada</strong>."
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

    reason_text = f" Motivo: {reason}." if reason else ""
    return Notification(
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        event_type=NotificationEventTypeEnum.internship_rejected,
        subject="Práctica rechazada",
        content=(
            f"Su práctica en <strong>{org_name}</strong> ha sido "
            f"<strong>rechazada</strong>.{reason_text}"
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

    reason_text = f" Motivo: {reason}." if reason else ""
    return Notification(
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        event_type=NotificationEventTypeEnum.internship_derived,
        subject="Práctica derivada a DIRAE",
        content=(
            f"Su práctica en <strong>{org_name}</strong> ha sido "
            f"<strong>derivada a DIRAE</strong> para revisión.{reason_text}"
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
        content=(
            f"Se registró una nueva práctica en <strong>{org_name}</strong> "
            "pendiente de revisión."
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
        content=(
            f"Se cargó el documento <strong>{document_type}</strong> "
            f"(<strong>{file_name}</strong>) para la práctica en "
            f"<strong>{org_name}</strong>."
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
    comment_text = f" Observación: {comment}." if comment else ""

    return Notification(
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        event_type=NotificationEventTypeEnum.custom,
        subject=f"Documento {status_label}: {document_type}",
        content=(
            f"Su documento <strong>{document_type}</strong> fue "
            f"<strong>{status_label}</strong>.{comment_text}"
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
        content=(
            f"El requisito <strong>{requirement_type}</strong> ha cambiado "
            f"su estado a <strong>{new_status}</strong>."
        ),
        status=status,
        payload={
            "requirement_id": requirement_id,
            "requirement_type": requirement_type,
            "new_status": new_status,
            "previous_status": previous_status,
        },
    )
