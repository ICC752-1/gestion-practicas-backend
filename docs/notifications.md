# Notificaciones

## Lectura persistente

La tabla `notification` registra `read_at` por notificacion y destinatario. Una
notificacion se considera no leida cuando `read_at IS NULL`.

Para bases locales existentes sin Alembic:

```sql
ALTER TABLE notification ADD COLUMN IF NOT EXISTS read_at TIMESTAMP;
CREATE INDEX IF NOT EXISTS ix_notification_recipient_user_id ON notification(recipient_user_id);
CREATE INDEX IF NOT EXISTS ix_notification_read_at ON notification(read_at);
```

## Contrato de listado

`GET /notifications` devuelve paginacion y contador persistente:

```json
{
  "items": [],
  "total": 0,
  "unread_count": 0,
  "limit": 50,
  "offset": 0
}
```

Filtros disponibles:

- `is_read`: `true` o `false`.
- `event_type`: tipo de evento de notificacion.
- `created_from`: fecha/hora minima.
- `created_to`: fecha/hora maxima.
- `limit` y `offset`: paginacion.

## Endpoints de lectura

- `GET /notifications/unread-count`: contador persistente sin descargar historial.
- `PATCH /notifications/{notification_id}/read`: marca una notificacion propia.
- `PATCH /notifications/read`: marca una seleccion propia con `notification_ids`.
- `PATCH /notifications/read-all`: marca todas las notificaciones propias.

Las operaciones son idempotentes y siempre filtran por el usuario autenticado;
conocer el ID de una notificacion ajena no permite modificar su lectura.
