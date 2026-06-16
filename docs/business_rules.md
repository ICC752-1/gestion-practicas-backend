# Reglas de Negocio: Gestión de Prácticas

## RN-01: Obligatoriedad de Seguro Escolar según Período de Práctica

### Descripción

La validación del seguro escolar garantiza que una práctica estival no sea
autorizada formalmente sin cobertura institucional o una excepción
administrativa trazable.

Para esta regla se distinguen dos momentos:

- **Creación de solicitud:** `POST /internships` registra los antecedentes en
  estado `Pendiente`. Todavía no autoriza al estudiante a iniciar la práctica.
- **Formalización:** una transición administrativa que deja la práctica en
  estado `Aprobada`. En este momento se aplican los requisitos obligatorios.

### Definición de la Regla

- **Práctica Semestral (`internship_period = "Semestre"`):** el seguro escolar
  no bloquea la creación ni la aprobación de la práctica.

- **Práctica Estival (`internship_period = "Verano"` o `"Invierno"`):** se
  permite crear y revisar la solicitud, pero no puede quedar `Aprobada` si el
  estudiante no tiene seguro escolar institucional vigente ni una excepción
  administrativa para esa práctica.

La creación en estado `Pendiente` no representa inscripción académica,
habilitación para iniciar actividades ni confirmación de cobertura.

### Base Legal y Contexto Institucional

- **Decreto Supremo N° 313:** Incluye a los estudiantes en el Seguro Escolar contra Accidentes del Trabajo y Enfermedades Profesionales de forma regular durante el año académico.

- **Reglamento de Prácticas FICA:** Dispone que toda actividad realizada fuera del periodo académico ordinario (periodo estival) requiere una extensión explícita de la cobertura del seguro para resguardar la integridad del alumno y la responsabilidad de la institución.

### Fuente de verdad institucional

- El estudiante no declara ni puede enviar `has_school_insurance` en
  `POST /internships`.
- La fuente de verdad es `student_registration_requirements`, usando
  `requirement = "school_insurance"` e `is_completed`.
- `Internship.has_school_insurance` es una copia de compatibilidad calculada por
  backend. No debe usarse como fuente autoritativa para aprobar.
- Al intentar la aprobación final, el backend vuelve a consultar el requisito
  institucional vigente. Así, una cobertura regularizada después de crear la
  solicitud permite continuar sin recrearla.

### Gestión administrativa del seguro

Los roles `Encargado de practica` y `Director de carrera` pueden consultar y
actualizar el requisito institucional mediante:

- `GET /admin/students/{student_id}/registration-requirements`
- `PATCH /admin/students/{student_id}/registration-requirements/school-insurance`

El `PATCH` crea el requisito si todavía no existe y registra `completed_at` y
`updated_by`. Enviar `is_completed = false` revoca el cumplimiento registrado y
limpia `completed_at`.

### Excepción Administrativa 
 
- Cuando una práctica estival no cuenta con seguro institucional vigente, un
  actor autorizado puede registrar una excepción justificada para esa práctica.

#### Principio de invariante
 
- La excepción no modifica `student_registration_requirements.is_completed` ni
  implica que el seguro exista. Solo autoriza el desvío para la práctica
  indicada y conserva la justificación y el responsable.
 
#### Roles autorizados para otorgar la excepción
 
| Rol | Puede otorgar excepción (`grant_exception`) |
| :--- | :---: |
| Encargado de práctica | **Sí** |
| Director de carrera | **Sí** |
| Secretaria de Carrera | No |
| Estudiante | No |
 
#### Condición de disparo
 
La excepción solo es relevante cuando se cumplen estas condiciones:
 
1. `internship_period` es `"Verano"` o `"Invierno"`.
2. El requisito institucional `school_insurance` no está completado.
3. La acción `approve` dejaría la práctica en estado `Aprobada`.

Una llamada a `approve` que solo produce `Pendiente -> En revisión` no queda
bloqueada por esta regla. Si la transición final intenta llegar a `Aprobada` sin
seguro ni excepción, el sistema responde `409 Conflict`.
 
#### Idempotencia
 
Si ya existe una excepción registrada para la misma práctica y regla, el endpoint retorna la existente sin crear un duplicado.
#### Restricción de estado terminal

No se puede registrar una excepción sobre una práctica en estado terminal (`Aprobada`, `Rechazada`, `Reprobada`).

#### Permanencia de la excepción

En esta versión, las excepciones administrativas son **permanentes**:
- No tienen vigencia configurable (no existe campo `expires_at` ni `is_active`).
- No existe mecanismo de revocación desde la API.
- Una excepción mal otorgada solo puede eliminarse físicamente desde la base de datos.

Esta es una decisión de diseño consciente, pendiente de revisión en una tarea futura si el negocio requiere expiración o revocación.

---

## Especificación Técnica

### Endpoint: `POST /internships`

#### Caso 1 — Crear solicitud estival sin seguro

La solicitud se crea en estado `Pendiente`. Esta operación no formaliza la
práctica y no exige seguro.

**Respuesta:** `201 Created`

#### Caso 2 — Enviar solicitud estival a revisión sin seguro

Si `POST /internships/{internship_id}/approve` produce solamente
`Pendiente -> En revisión`, la operación se permite.

**Respuesta:** `200 OK`, con estado `En revisión`.

---

### Endpoint: `POST /internships/{internship_id}/approve`

#### Caso 3 — Rechazo de aprobación final estival sin seguro

Cuando la transición dejaría la práctica en `Aprobada`, el backend consulta el
requisito institucional vigente. Si no está completado y no existe excepción:

**Respuesta:** `409 Conflict`

```json
{
  "detail": {
    "rule": "school_insurance",
    "message": "La práctica es estival y no cuenta con seguro escolar. Se requiere una excepción administrativa registrada para continuar (D.S. 313)."
  }
}
```

#### Caso 4 — Práctica semestral

La solicitud y su aprobación se permiten sin seguro escolar.

#### Caso 5 — Práctica estival con seguro regularizado

Si el seguro se registra después de crear la solicitud y antes de su aprobación
final, la consulta vigente permite aprobarla. No es necesario crear otra
práctica.

#### Caso 6 — Práctica estival con excepción

Una excepción `school_insurance` permite la aprobación final, pero el requisito
institucional permanece incompleto.

---

## RN-01-B: Una solicitud bloqueante por estudiante y tipo de práctica

### Descripción

Un estudiante no puede mantener más de una solicitud vigente para el mismo
`internship_type`. La regla evita duplicidad funcional y protege también
peticiones concurrentes desde dos pestañas o clientes distintos.

### Definición de la regla

Bloquean nuevas solicitudes del mismo tipo las prácticas con
`blocks_new_registration = true`. En el ciclo actual esto incluye solicitudes en
`Pendiente`, `En revisión`, `En revisión DIRAE` y `Aprobada`, salvo que el
cierre final de la práctica sea `completion_status=finalized` y
`final_result=failed`.

El bloqueo se libera cuando la solicitud es `Rechazada` o anulada lógicamente
con `is_cancelled = true`. También se libera cuando una práctica finaliza con
`final_result=failed`. Una práctica aprobada o finalizada con `final_result=passed`
mantiene el bloqueo para evitar repetir un tipo ya aprobado.

### Garantía persistente

La base de datos mantiene el índice único parcial
`uq_internship_blocking_type_per_student` sobre `user_id + internship_type`
cuando `blocks_new_registration IS TRUE` y el cierre final no corresponde a
`finalized/failed`. La consulta previa del servicio mejora el mensaje de error,
pero la invariancia no depende solo del frontend ni de una lectura previa.

### Contrato de error

`POST /internships` responde `409 Conflict` cuando ya existe una solicitud
bloqueante:

```json
{
  "detail": {
    "code": "duplicate_internship_type",
    "existing_internship_id": 15,
    "internship_type": "Práctica de Estudio I",
    "existing_status": "Pendiente",
    "message": "Ya existe una solicitud vigente para este tipo de práctica. Revisa el registro existente antes de crear una nueva solicitud."
  }
}
```

`GET /internships/registration-eligibility` expone el diagnóstico preventivo
con `has_blocking_internship`, `blocking_internship_id`,
`blocking_internship_status` y `can_create_request`.

---

## RN-01-C: Agenda de entrevistas y presentaciones sin doble reserva

### Descripción

La agenda institucional usa `Presentation` como fuente única para representar
bloques publicados, reservas de entrevista inicial y reservas de presentación
final. No se deben mantener horarios reales solo en estado local del frontend.

### Definición de la regla

- Los roles `Encargado de practica` y `Director de carrera` pueden publicar
  disponibilidad futura asociada a su propio usuario.
- Cada bloque contiene fecha, hora inicial, hora final, duración, modalidad,
  ubicación/enlace, zona horaria, propietario y propósito.
- Un estudiante solo puede reservar un bloque `available` para una práctica
  propia y no anulada.
- Una práctica no puede tener dos citas activas para el mismo propósito.
- Un estudiante no puede mantener citas solapadas.
- Un administrativo no puede publicar disponibilidad que se solape con otro
  bloque activo propio.
- Un bloque pasado no puede reservarse ni cerrarse desde la API.

### Garantía de concurrencia

La reserva toma el bloque con bloqueo de fila y vuelve a validar que siga en
estado `available` antes de asignar `user_id`, `internship_id`, `reserved_at` y
`status=scheduled`. Además, la base de datos mantiene un índice único parcial
por propietario, fecha, rango horario y propósito para bloques activos.

### Cancelación y reprogramación

El estudiante propietario puede cancelar o reprogramar su cita. Un rol
administrativo solo puede cancelar o cerrar bloques propios; cuando cancela una
cita ya agendada debe entregar motivo.

---

## RN-02: Matriz de Transiciones de Estados y Permisología por Rol

### Descripción

El flujo de evaluación de una solicitud de práctica está diseñado bajo un modelo de **concurrencia jerárquica no secuencial obligatoria**. Esto asegura que el Director de Carrera mantenga la facultad de resolver solicitudes de manera inmediata sin depender de pasos intermedios, evitando cuellos de botella en la gestión de la Escuela, mientras se preserva el estado de revisión para auditoría y trazabilidad ordinaria.

### Definición de la Regla

1. **Flexibilidad del Flujo Inicial:** Una práctica en estado `Pendiente` puede transicionar directamente a `Aprobada` o `Rechazada` sin obligar al registro de la etapa intermedia `En revisión`.
2. **Jerarquía Concurrente de Aprobación:** Tanto el **Encargado de Práctica** como el **Director de Carrera** poseen permisos idénticos para las acciones de aprobación (`approve`) y rechazo (`reject`), variando únicamente el impacto automático en el estado de destino para solicitudes nuevas.
3. **Desacoplamiento de Gestión Documental:** El rol de **Secretaría de Carrera** interviene exclusivamente en la fase de tramitación documental posterior o paralela mediante la acción de derivación (`derive`). Secretaría **no posee** facultades para dictaminar la aprobación o rechazo técnico-académico de la práctica.

### Matriz de Permisología Funcional

| Origen | Destino | Acción Funcional | Encargado de Práctica | Director de Carrera | Secretaría de Carrera |
| :--- | :--- | :--- | :---: | :---: | :---: |
| `Pendiente` | `En revisión` | `approve` (flujo regular) | **Sí** | **Sí** | No |
| `Pendiente` | `Aprobada` | `approve` (`skip_review=True` / Directo) | **Sí** | **Sí** | No |
| `Pendiente` | `Rechazada` | `reject` | **Sí** | **Sí** | No |
| `En revisión` | `Aprobada` | `approve` | **Sí** | **Sí** | No |
| `En revisión` | `Rechazada` | `reject` | **Sí** | **Sí** | No |
| `Pendiente` o `En revisión` | `En revisión DIRAE` | `derive` | Según regla documental | Según regla documental | **Sí** |

> [!WARNING]
> **Criterio de Restricción Terminal:** Los estados `Aprobada`, `Rechazada` y `Reprobada (Legacy)` son estrictamente **terminales**. Cualquier intento de aplicar una acción administrativa sobre ellos gatillará un rechazo inmediato por consistencia de datos (`409 Conflict`).

---

## RN-03: Secuencialidad de Prácticas (Práctica I → Práctica II)

### Descripción

Un estudiante no puede avanzar la **Práctica de Estudio II** mediante `approve()` mientras su **Práctica de Estudio I** no se encuentre aprobada. La creación de la Práctica II (`create_internship`) no está sujeta a esta restricción.

La inducción obligatoria aprobada habilita la creación de solicitudes desde el
flujo estudiante. Además, la **Práctica de Estudio I** exige inducción aprobada
antes de la aprobación administrativa. Esta regla es inexceptuable: no puede
resolverse con una excepción administrativa.

### Definición de la Regla

- `create_internship` responde `409 Conflict` con `code=induction_required` si
  el estudiante no tiene inducción aprobada.
- Si la práctica en aprobación es de tipo `Práctica de Estudio I`, el sistema verifica que el estudiante tenga inducción aprobada en `student_registration_requirements` o un intento aprobado en `induction_attempts`.
- Si no existe inducción aprobada para Práctica I, se bloquea el avance con `409 Conflict`.
- Una inducción histórica aprobada sigue siendo válida salvo que la versión
  activa tenga `requires_retake=true`; en ese caso debe existir un intento
  aprobado para la versión activa.
- Si la práctica en aprobación es de tipo `Práctica de Estudio II`, el sistema verifica que el estudiante tenga al menos una `Práctica de Estudio I` con estado `Aprobada`.
- Si no existe dicha práctica I aprobada, se bloquea el avance con `409 Conflict`.
- El bloqueo puede omitirse mediante una excepción administrativa de tipo `"sequentiality"`.
- La creación de una solicitud de Práctica II se permite sin restricciones de secuencialidad, pero no podrá formalizarse hasta cumplir la regla u obtener una excepción.

> **Nota técnica:** La regla actual considera el estado `Aprobada` como criterio oficial para satisfacer la secuencialidad. Si negocio define otro hito académico en el futuro (ej. "Evaluación aprobada" como hito intermedio), la regla deberá ajustarse.

### Excepción Administrativa

- Cuando no existe una Práctica I aprobada, un actor administrativo autorizado puede registrar una excepción de secuencialidad que habilita el trámite sin modificar el estado de la Práctica I.
- La excepción se registra sobre la **Práctica II** (la que se intenta aprobar).

#### Roles autorizados para otorgar la excepción

| Rol | Puede otorgar excepción (`grant_exception`) |
| :--- | :---: |
| Encargado de práctica | **Sí** |
| Director de carrera | **Sí** |
| Secretaria de Carrera | No |
| Estudiante | No |

#### Condición de disparo

1. `internship_type` es `"Práctica de Estudio II"`.
2. El estudiante **no** tiene una `Práctica de Estudio I` en estado `Aprobada`.
3. El actor intenta aprobar la práctica (acción `approve`).

Sin una excepción activa para la regla `sequentiality`, el sistema bloquea con `409 Conflict`.

#### Idempotencia

Si ya existe una excepción registrada para la misma práctica y regla `sequentiality`, el endpoint retorna la existente sin crear un duplicado.

#### Restricción de estado terminal

No se puede registrar una excepción sobre una práctica en estado terminal (`Aprobada`, `Rechazada`, `Reprobada`).

#### Permanencia de la excepción

En esta versión, las excepciones administrativas son **permanentes**:
- No tienen vigencia configurable (no existe campo `expires_at` ni `is_active`).
- No existe mecanismo de revocación desde la API.
- Una excepción mal otorgada solo puede eliminarse físicamente desde la base de datos.

Esta es una decisión de diseño consciente, pendiente de revisión en una tarea futura si el negocio requiere expiración o revocación.

---


### Endpoint: `POST /internships/{internship_id}/exceptions`
 
#### Caso 4 — Éxito: Excepción registrada
 
**Roles:** `Encargado de práctica`, `Director de carrera`
 
**Request:**
 
```json
{
  "rule": "school_insurance",
  "reason": "Póliza en proceso de firma. Documentación física recibida por Secretaría."
}
```
 
**Respuesta:** `201 Created`
 
```json
{
  "id": 1,
  "internship_id": 15,
  "rule": "school_insurance",
  "reason": "Póliza en proceso de firma. Documentación física recibida por Secretaría.",
  "authorized_by": {
    "id": 5,
    "email": "encargado@ufro.cl",
    "first_name": "Juan",
    "last_name": "Coordinador"
  },
  "authorized_at": "2026-06-09T14:30:00"
}
```
 
#### Caso 5 — Rechazo: Regla no exceptuable
 
**Respuesta:** `400 Bad Request`
 
```json
{
  "detail": "La regla 'invalid_rule' no admite excepción administrativa."
}
```
 
#### Caso 6 — Rechazo: Práctica en estado terminal
 
**Respuesta:** `409 Conflict`
 
```json
{
  "detail": "No se puede registrar una excepción sobre una práctica en estado terminal: Aprobada."
}
```
 
#### Caso 7 — Rechazo: Sin permiso
 
**Respuesta:** `403 Forbidden`
 
```json
{
  "detail": "Insufficient permissions"
}
```
 
### Endpoint: `POST /internships/{internship_id}/approve` (aprobación final estival)
 
#### Caso 8 — Rechazo: transición a `Aprobada` sin seguro ni excepción
 
**Respuesta:** `409 Conflict`
 
```json
{
  "detail": {
    "rule": "school_insurance",
    "message": "La práctica es estival y no cuenta con seguro escolar. Se requiere una excepción administrativa registrada para continuar (D.S. 313)."
  }
}
```
---


## RN-04: Gestión Documental por Propiedad, Rol y Estado

### Descripción

La gestión documental centraliza los respaldos de práctica dentro de la
plataforma para reducir correos, proteger la privacidad del estudiante y dejar
base para Secretaría y DIRAE. El backend es responsable de validar que cada
archivo pertenezca a una práctica real y que solo usuarios autorizados puedan
consultarlo, revisarlo o eliminarlo.

### Definición de la Regla

1. **Propiedad estudiantil:** Un estudiante solo puede cargar, listar, descargar
   o eliminar documentos asociados a sus propias prácticas.
2. **Roles documentales:** `Encargado de practica`, `Director de carrera` y
   `Secretaria de Carrera` pueden listar, descargar, observar y aprobar
   documentos de una práctica.
3. **Separación funcional de Secretaría:** Secretaría puede gestionar documentos
   y preparar el flujo documental, pero no obtiene por esta regla permisos para
   aprobar o rechazar la práctica.
4. **Bloqueo por estado terminal:** No se permite cargar documentos nuevos si la
   práctica está `Aprobada`, `Rechazada` o `Reprobada`.
5. **Corrección documental:** Se permite cargar documentos en `Pendiente`,
   `En revisión` y `En revisión DIRAE`.
6. **Eliminación lógica:** Los documentos no se borran de la base de datos. La
   eliminación registra `deleted_at`, `deleted_by` y estado `deleted`.
7. **Documento aprobado:** Un estudiante no puede eliminar un documento aprobado;
   un rol documental autorizado sí puede marcarlo como eliminado.

### Matriz de Permisología Documental

| Acción | Estudiante propietario | Otro estudiante | Encargado | Director | Secretaría |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Cargar documento | Sí, si práctica no terminal | No | No | No | No |
| Listar documentos | Sí | No | Sí | Sí | Sí |
| Descargar documento | Sí | No | Sí | Sí | Sí |
| Observar documento | No | No | Sí | Sí | Sí |
| Aprobar documento | No | No | Sí | Sí | Sí |
| Eliminar documento no aprobado | Sí | No | Sí | Sí | Sí |
| Eliminar documento aprobado | No | No | Sí | Sí | Sí |

## RN-05: Secuencialidad de Titulación (Tesis)

### Descripción

Un estudiante no puede avanzar la **Tesis** mediante `approve()` mientras su
**Práctica de Estudio II** no se encuentre aprobada. La creación de la Tesis
(`create_internship`) no está sujeta a esta restricción.

### Definición de la Regla

- La validación se aplica **exclusivamente al momento de aprobación** (`approve`),
  no a la creación inicial de la solicitud (`create_internship`).
- Si la práctica en aprobación es de tipo `Tesis`, el sistema verifica que el
  estudiante tenga al menos una `Práctica de Estudio II` con estado `Aprobada`
  en `StudentInternshipRequirement`.
- Si no existe dicha práctica II aprobada, se bloquea el avance con `409 Conflict`.
- El bloqueo puede omitirse mediante una excepción administrativa de tipo
  `"sequentiality_thesis"`.

### Excepción Administrativa

- Cuando no existe una Práctica II aprobada, un actor administrativo autorizado
  puede registrar una excepción de secuencialidad (`sequentiality_thesis`) que
  habilita el trámite sin modificar el estado de la Práctica II.
- La excepción se registra sobre la **Tesis** (la que se intenta aprobar).

#### Roles autorizados

| Rol | Puede otorgar excepción (`grant_exception`) |
| :--- | :---: |
| Encargado de práctica | **Sí** |
| Director de carrera | **Sí** |
| Secretaria de Carrera | No |
| Estudiante | No |

#### Condición de disparo

1. `internship_type` es `"Tesis"`.
2. El estudiante **no** tiene una `Práctica de Estudio II` en estado `Aprobada`
   en `StudentInternshipRequirement`.
3. El actor intenta aprobar la práctica (acción `approve`).

Sin una excepción activa para la regla `sequentiality_thesis`, el sistema
bloquea con `409 Conflict`.

---

## RN-06: Práctica Controlada y Rama en Paralelo

### Descripción

La **Práctica Controlada** requiere que los co-requisitos (ramos cursados en
paralelo) estén resueltos. Como el sistema aún no modela la malla curricular,
se asume que hay co-requisitos pendientes y se exige una excepción
administrativa para permitir el avance.

### Definición de la Regla

- La validación se aplica **exclusivamente al momento de aprobación** (`approve`),
  no a la creación inicial de la solicitud (`create_internship`).
- Si la práctica en aprobación es de tipo `Práctica Controlada`, el sistema
  exige una excepción administrativa de tipo `"parallel_course"`.
- Sin la excepción, el sistema bloquea el avance con `409 Conflict`.

### Excepción Administrativa

- Un actor administrativo autorizado puede registrar una excepción
  (`parallel_course`) que habilita el trámite.
- La excepción se registra sobre la **Práctica Controlada**.

#### Roles autorizados

| Rol | Puede otorgar excepción (`grant_exception`) |
| :--- | :---: |
| Encargado de práctica | **Sí** |
| Director de carrera | **Sí** |
| Secretaria de Carrera | No |
| Estudiante | No |

#### Condición de disparo

1. `internship_type` es `"Práctica Controlada"`.
2. El actor intenta aprobar la práctica (acción `approve`).

Sin una excepción activa para la regla `parallel_course`, el sistema bloquea con
`409 Conflict`.

---

### Restricciones Técnicas

- Extensiones permitidas: `pdf`, `docx`, `jpg`, `png`, `zip`.
- Tamaño máximo inicial: `10485760` bytes por archivo.
- El campo `file_path` es una clave interna de storage privado y no debe
  exponerse en respuestas JSON.
- Las descargas siempre pasan por `GET /documents/{document_id}/download` con
  autenticación y autorización.
- La eliminacion documental es logica; el archivo fisico se conserva mientras no
  exista una politica institucional de retencion y limpieza fisica.
- En produccion VPS, el storage documental debe montarse como volumen persistente
  privado y no debe exponerse como contenido estatico por Nginx.

Para la politica operacional completa revisar `docs/documents-privacy.md`.

---

## RN-04: Exportación DIRAE posterior a la aprobación administrativa

### Descripción

La exportación DIRAE consolida prácticas ya aprobadas y con documentación
mínima validada. El paquete documental es una vista calculada sobre prácticas,
estudiantes, tipos documentales y documentos aprobados; no representa una etapa
obligatoria para resolver la solicitud de práctica.

### Definición de la Regla

1. **Aprobación previa:** Una práctica solo puede ser exportable a DIRAE cuando
   su estado actual es `Aprobada`.
2. **Documentación requerida:** Todos los tipos documentales activos marcados
   como requeridos deben tener al menos un documento `approved` no eliminado.
3. **Documento vigente por tipo:** Si existen varios documentos aprobados para
   un mismo tipo, se selecciona el más reciente por `upload_date DESC, id DESC`.
4. **DIRAE no bloquea la aprobación:** El flujo DIRAE ocurre después de la
   aprobación administrativa. No es un estado previo obligatorio para aprobar
   o rechazar una práctica.
5. **Roles autorizados:** `Encargado de practica`, `Director de carrera` y
   `Secretaria de Carrera` pueden consultar paquetes documentales y exportar
   CSV DIRAE.
6. **Matrícula derivada:** La matrícula institucional se calcula como RUT sin
   puntos ni guion más los dos últimos dígitos del año de ingreso cuando ese dato
   está disponible. Si el año de ingreso no existe en el modelo actual, el campo
   queda vacío o `null`.
7. **Sin persistencia de lote MVP:** La exportación se genera dinámicamente y no
   crea lotes persistidos en esta versión.
8. **Evento auditable definido:** La exportación deja definido el evento
   `dirae_export_generated` con actor, fecha, prácticas, documentos, archivo y
   resultado para integrarlo con la auditoría funcional cuando 11.5 esté
   disponible.

### Resultado Técnico

- `GET /internships/{internship_id}/documents/package` retorna
  `exportable = false` con razones estables si la práctica no está aprobada o
  faltan documentos requeridos.
- `GET /dirae/document-packages/export` retorna CSV `text/csv`. Cuando se
  solicitan IDs explícitos, una práctica inexistente responde `404` y una
  práctica no exportable responde `409`.

---
