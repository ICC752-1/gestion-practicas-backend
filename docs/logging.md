<h1 align="center"><em>Logging</em></h1>

> [!NOTE]
> Esta documentación describe la configuración real implementada en el código actual,
> no conceptos genéricos de logging.

## Contenidos
- [Resumen operativo](#resumen-operativo)
- [Flujo de inicialización](#flujo-de-inicialización)
- [Enrutamiento por severidad y destino](#enrutamiento-por-severidad-y-destino)
- [Formato de salida](#formato-de-salida)
- [Configuración por entorno](#configuración-por-entorno)
- [Eventos actuales registrados](#eventos-actuales-registrados)
- [Consideraciones operativas](#consideraciones-operativas)

---

## Resumen operativo

El sistema se inicializa al cargar la aplicación en `app/main.py` mediante
`setup_logging()`. A partir de ese punto:

- Consola en texto plano.
- Separación de `stdout` y `stderr` por severidad.
- Persistencia en archivos JSONL rotativos.
- Archivo separado exclusivo para errores.
- Prevención de duplicados si ya está configurado.

> [!TIP]
> Toda emisión que use `logging.getLogger(__name__)` entra automáticamente al
> circuito global.

---

## Flujo de inicialización

1. **Arranque de la app**
   - `app/main.py` llama `setup_logging()` y crea su logger local.

2. **Detección de configuración previa**
   - Dentro de `app/core/logging/logging.py`, `_is_logging_already_configured()`
     inspecciona los handlers del root logger (el logger global al que propagan
     los demás loggers).
   - Aquí, `baseFilename` es el atributo que expone el `RotatingFileHandler`
     (el handler que escribe a archivo y rota por tamaño) con la ruta absoluta
     del archivo donde está escribiendo.
   - Se compara `baseFilename` con las rutas esperadas de los archivos de log del
     proyecto para confirmar si ya existen handlers propios activos.
   - Si alguno coincide, se considera que la configuración ya está aplicada y
     `setup_logging()` termina sin volver a registrar handlers.

3. **Carga de configuración base**
   - Se lee `app/core/logging/logging_config.json`, el cual contiene los filtros,
     formatters, handlers y loggers predefinidos.

4. **Overrides en runtime**
   - Se aplican valores de entorno sobre:
     - nivel raíz
     - rutas de archivos
     - rotación por tamaño y backups

5. **Aplicación final**
   - Se ejecuta `logging.config.dictConfig(...)` para registrar esa estructura
     dentro del sistema de logging de Python y activarla en toda la app.

> [!IMPORTANT]
> Evitar la reconfiguración evita duplicados: si se agregan handlers otra vez,
> cada evento se escribe varias veces en consola y archivos.
>
> En esta implementación se verifica el root logger y, si ya hay handlers
> propios, se corta el flujo antes de `dictConfig(...)`.

---

## Enrutamiento por severidad y destino

### Destinos definidos en el root logger

Aquí se definen los destinos de salida (handlers) que recibirán todo lo que
propague al root logger. Los filtros son reglas de paso que permiten o bloquean
registros según el nivel de severidad.

| Handler | Tipo | Filtro | Destino | Formato |
| --- | --- | --- | --- | --- |
| `stdout` | Stream | `below_warning` | `sys.stdout` | texto |
| `stderr` | Stream | `warning_and_above` | `sys.stderr` | texto |
| `file` | RotatingFile | - | JSONL general | JSON |
| `error_file` | RotatingFile | `error_and_above` | JSONL errores | JSON |

### Matriz de comportamiento por nivel

Esta matriz resume el efecto combinado de los filtros y el root logger. En la
práctica responde a: *«si emito un log con este nivel, ¿a qué destinos va a parar?»*

| Nivel | stdout | stderr | archivo general | archivo errores |
| --- | --- | --- | --- | --- |
| DEBUG | sí | no | sí | no |
| INFO | sí | no | sí | no |
| WARNING | no | sí | sí | no |
| ERROR | no | sí | sí | sí |
| CRITICAL | no | sí | sí | sí |

> [!NOTE]
> El archivo general siempre recibe todo lo que llega al root logger.

---

## Formato de salida

### Consola (texto plano)

```text
%(asctime)s [%(levelname)s] %(name)s (%(module)s:%(lineno)d) - %(message)s
```

### Archivos (JSONL)

- Una línea JSON por evento.
- `timestamp` en UTC con ISO 8601.
- Se incluyen `exc_info` o `stack_info` si existen.
- Serializa con `ensure_ascii=False`.

Campos mapeados:

- `timestamp`
- `level`
- `logger`
- `module`
- `function`
- `line`
- `thread`
- `message`

Ejemplo de línea JSON:

```json
{"timestamp":"2026-05-13T10:15:30.123456+00:00","level":"INFO","logger":"app.main","module":"main","function":"lifespan","line":42,"thread":140012345678912,"message":"Application startup completed"}
```

> [!NOTE]
> ISO 8601 en UTC es un estándar interoperable: hace que los timestamps sean
> comparables entre servicios, evita ambigüedades de zona horaria y permite
> ordenar eventos de forma consistente en sistemas distribuidos.

> [!TIP]
> JSONL facilita ingestión por herramientas externas sin parsear texto de consola.

---

## Configuración por entorno

Valores por defecto en `app/core/config.py`:

| Variable | Default | Uso |
| --- | --- | --- |
| `LOG_DIR` | `logs` | directorio base |
| `LOG_FILE_NAME` | `gestion_practicas.jsonl` | archivo general |
| `LOG_ERROR_FILE_NAME` | `gestion_practicas_errors.jsonl` | archivo de errores |
| `LOG_LEVEL` | `INFO` | nivel raíz |
| `LOG_MAX_BYTES` | `10485760` | tamaño antes de rotar |
| `LOG_BACKUP_COUNT` | `5` | backups por archivo |

### Rotación

Ambos archivos (general y errores) usan `RotatingFileHandler`:

`RotatingFileHandler` es el handler de Python que escribe en archivo y aplica
rotación por tamaño, creando copias de respaldo cuando el archivo supera el
límite configurado.

- rotan al alcanzar `LOG_MAX_BYTES`
- conservan hasta `LOG_BACKUP_COUNT` copias

> [!WARNING]
> Un `LOG_LEVEL` alto (por ejemplo `WARNING`) reduce visibilidad en consola y
> archivo general porque se descartan niveles informativos antes de llegar a los
> handlers.

---

## Eventos actuales registrados

### Ciclo de vida (app)

- `Application startup completed`
- `Application shutdown completed`

### Autenticación (controlador)

- `Login request received`

### Autenticación (servicio)

- `Login attempt failed: user not found`
- `Login attempt failed: invalid credentials`
- `User authenticated successfully`

### Dependencia de seguridad

- `JWT token expired`
- `Invalid JWT token`
- `JWT token payload is missing subject`
- `JWT token subject is invalid`
- `User from JWT token was not found`
- `Inactive user attempted to access a protected endpoint`
- `Unexpected error while decoding JWT token` (con `exc_info=True`)

---

## Consideraciones operativas

> [!NOTE]
> `disable_existing_loggers = false` mantiene loggers previos activos para no
> perder eventos ya configurados por librerías externas.

> [!IMPORTANT]
> `uvicorn`, `uvicorn.error`, `uvicorn.access` propagan al root y siguen el mismo
> enrutamiento, de modo que sus eventos quedan en los mismos destinos que los de
> la aplicación.

> [!TIP]
> La separación `stdout` vs `stderr` facilita redirecciones y observabilidad en
> entornos con colectores de logs.

> [!WARNING]
> Si `setup_logging()` se ejecutara sin el guardado de handlers, se duplicarían
> registros en consola y archivos porque cada nueva configuración agregaría
> handlers adicionales sin reemplazar los anteriores.
