# Notificaciones

Esta documentacion describe los eventos de notificacion actualmente soportados,
los payloads minimos persistidos y el comportamiento del servicio ante fallos.

## Modos

El modo se controla con `NOTIFICATION_MODE`.

| Modo | Comportamiento |
| --- | --- |
| `simulated` | Persiste la notificacion con `status=simulated` y no envia SMTP. Es el valor por defecto para desarrollo y pruebas. |
| `real` | Persiste la notificacion con `status=pending`, intenta envio SMTP y luego actualiza a `sent` o `failed`. |

Si `NOTIFICATION_MODE=real` pero las credenciales SMTP siguen en valores por defecto,
el servicio no construye mailer y opera efectivamente como flujo simulado.

## Persistencia

Cada notificacion se persiste en la tabla `notification` con estos campos clave:

| Campo | Descripcion |
| --- | --- |
| `recipient_user_id` | Usuario interno destinatario, si aplica. |
| `recipient_email` | Correo destino para envio real SMTP, si aplica. |
| `event_type` | Tipo de evento almacenado en el enum de notificaciones. |
| `subject` | Asunto visible. |
| `content` | Cuerpo HTML/texto de la notificacion. |
| `status` | `simulated`, `pending`, `sent` o `failed`. |
| `payload` | Metadata minima para correlacionar con practica, documento o requisito. |
| `sent_at` | Fecha de envio real; queda `null` en modo simulated y en fallos. |

## Eventos Soportados

| Evento funcional | `event_type` | Emisor | Destinatario | Referencias minimas |
| --- | --- | --- | --- | --- |
| Registro de practica | `custom` | `InternshipService.create_internship` | Revisores con rol `Encargado de practica` o `Director de carrera` | `internship_id`, `student_user_id` |
| Practica aprobada | `internship_approved` | `InternshipService.approve` | Estudiante propietario | `internship_id` |
| Practica rechazada | `internship_rejected` | `InternshipService.reject` | Estudiante propietario | `internship_id`, `reason` |
| Practica derivada a DIRAE | `internship_derived` | `InternshipService.derive` | Estudiante propietario | `internship_id`, `reason` |
| Documento cargado | `custom` | `DocumentService.upload_document` | Revisores documentales | `document_id`, `internship_id`, `document_type` |
| Documento observado | `custom` | `DocumentService.update_document_status` | Estudiante propietario | `document_id`, `internship_id`, `document_type`, `new_status`, `comment` |
| Documento aprobado | `custom` | `DocumentService.update_document_status` | Estudiante propietario | `document_id`, `internship_id`, `document_type`, `new_status`, `comment` |
| Requisito actualizado | `requirement_status_changed` | `AdminService.update_student_internship_requirement_status` | Estudiante propietario | `requirement_id`, `requirement_type`, `new_status`, `previous_status` |

Los eventos funcionales que usan `event_type=custom` incorporan el nombre del

## Payloads

### Registro De Practica

```json
{
  "event": "internship_created",
  "internship_id": 123,
  "student_user_id": 10
}
```

### Practica Aprobada

```json
{
  "internship_id": 123
}
```

### Practica Rechazada

```json
{
  "internship_id": 123,
  "reason": "No cumple requisitos"
}
```

### Practica Derivada

```json
{
  "internship_id": 123,
  "reason": "Requiere revision DIRAE"
}
```

### Documento Cargado

```json
{
  "event": "document_uploaded",
  "document_id": 55,
  "internship_id": 123,
  "document_type": "Formulario de inscripción"
}
```

### Documento Observado O Aprobado

```json
{
  "event": "document_status_changed",
  "document_id": 55,
  "internship_id": 123,
  "document_type": "Formulario de inscripción",
  "new_status": "observed",
  "comment": "Falta firma"
}
```

Para aprobacion documental, `new_status` es `approved` y `comment` puede ser
`null`.

### Requisito Actualizado

```json
{
  "requirement_id": 3,
  "requirement_type": "Práctica de Estudio I",
  "new_status": "Aprobada",
  "previous_status": "En revisión"
}
```

## Fallos

Los servicios de negocio tratan el despacho de notificaciones como un efecto
secundario no bloqueante.

Si `NotificationService.create_and_dispatch` falla durante un flujo de negocio:

1. La accion principal ya persistida no se revierte.
2. El error se registra en logs con `exc_info=True`.
3. El endpoint o servicio continua retornando el resultado funcional principal.

En modo `real`, si falla el envio SMTP despues de persistir la notificacion:

1. La notificacion se marca como `failed`.
2. `sent_at` queda `null`.
3. Puede reintentarse mediante el flujo de retry del modulo de notificaciones.

## Eventos Pendientes

Los siguientes eventos estan definidos como requerimiento funcional, pero aun no
tienen flujo de dominio implementado en el backend:

| Evento pendiente | Motivo |
| --- | --- |
| Solicitud de evaluacion al supervisor | No existe todavia el flujo de evaluacion de supervisor. |
| Recordatorio de entrevista | No existe todavia el flujo de entrevista/presentacion calendarizada. |
