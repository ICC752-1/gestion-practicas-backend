# Almacenamiento y privacidad documental

Este documento define la estrategia de almacenamiento documental para el modulo
`documents`, considerando despliegue productivo en una VPS administrada por el
equipo mediante acceso remoto.

## Estrategia de almacenamiento

El backend almacena archivos en filesystem privado. La base de datos conserva
solo metadatos y una clave interna `file_path`; esa clave no es una URL publica
ni se entrega en `DocumentResponse`.

Por entorno:

- Desarrollo local: `DOCUMENT_STORAGE_DIR=storage/documents` o el volumen local
  definido por Docker Compose.
- Produccion VPS: `DOCUMENT_STORAGE_DIR=/app/storage/documents`, montado como
  volumen persistente Docker o bind mount privado del host.

En `gestion-practicas-deployment/compose.prod.yml` el backend monta:

```yaml
${DOCUMENT_STORAGE_HOST_PATH:-backend_documents}:/app/storage/documents
```

Si `DOCUMENT_STORAGE_HOST_PATH` no se define, Docker crea y mantiene el volumen
`backend_documents`. Si se define, puede apuntar a una ruta del host como
`/srv/team-b/data/documents`, lo que facilita respaldos desde la VPS.

## Privacidad y acceso

Los documentos no se sirven como archivos estaticos por Nginx ni desde el
frontend. Toda descarga debe pasar por:

```text
GET /documents/{document_id}/download
```

Ese endpoint exige usuario autenticado y delega la autorizacion al servicio
documental. La politica vigente permite descarga solo a:

- estudiante propietario de la practica;
- `Encargado de practica`;
- `Director de carrera`;
- `Secretaria de Carrera`.

El campo `file_path` se considera informacion interna de storage. No debe
aparecer en respuestas JSON, logs funcionales ni URLs publicas.

## Modelo de amenaza en VPS

La privacidad aplicada por la aplicacion protege frente a usuarios finales,
accesos cruzados y solicitudes HTTP sin autorizacion. No reemplaza los controles
de infraestructura.

Un operador con acceso `root`, permisos Docker o acceso shell privilegiado a la
VPS podria leer archivos directamente desde el filesystem o los volumenes. Ese
riesgo debe gestionarse con control de acceso a la VPS, llaves SSH, permisos del
host y politicas operativas del equipo.

## Retencion

La variable `DOCUMENT_RETENTION_DAYS` documenta la politica de retencion deseada.
El valor inicial recomendado es `0`, que significa conservar documentos de forma
indefinida hasta que exista una politica institucional formal.

Reglas actuales:

- La eliminacion desde la aplicacion es logica: registra `deleted_at`,
  `deleted_by` y estado `deleted`.
- No existe borrado fisico automatico de archivos.
- Los documentos eliminados logicamente no pueden descargarse por la API.
- Cualquier limpieza fisica futura debe preservar trazabilidad y contar con una
  regla explicita de negocio.

## Operacion en VPS

Configuracion recomendada en `.env` productivo:

```env
DOCUMENT_STORAGE_DIR=/app/storage/documents
DOCUMENT_MAX_BYTES=10485760
DOCUMENT_ALLOWED_EXTENSIONS=pdf,docx,jpg,png,zip
DOCUMENT_RETENTION_DAYS=0
DOCUMENT_STORAGE_HOST_PATH=/srv/team-b/data/documents
```

Si se usa `DOCUMENT_STORAGE_HOST_PATH`, crear la ruta en la VPS antes de levantar
el stack y asignar permisos al usuario que ejecuta Docker:

```bash
sudo mkdir -p /srv/team-b/data/documents
```

La ruta documental debe incluirse en la estrategia de respaldo junto con la base
de datos PostgreSQL. Para restaurar el sistema se necesitan ambos componentes:
metadatos en base de datos y archivos fisicos del storage documental.

## Verificaciones esperadas

- El directorio documental no aparece en configuraciones de Nginx como root,
  alias ni location estatico.
- Una solicitud sin token a `/documents/{document_id}/download` responde `401`.
- Un estudiante distinto al propietario recibe `403`.
- El propietario o un rol documental autorizado puede descargar el archivo.
- Un documento eliminado logicamente o con archivo faltante responde `404`.
