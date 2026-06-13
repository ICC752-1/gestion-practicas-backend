# Reglas de Negocio: Gestión de Prácticas

## RN-01: Obligatoriedad de Seguro Escolar según Período de Práctica

### Descripción

La validación del seguro escolar garantiza la cobertura de accidentes de los estudiantes durante el desarrollo de sus actividades profesionales. La obligatoriedad de este seguro varía estrictamente según la naturaleza temporal del período en el que se ejecuta la práctica.

### Definición de la Regla

- **Práctica Semestral (`internship_period`: "Semestre"):** El seguro escolar **no es requerido** de forma obligatoria por parte de la plataforma para registrar la práctica, dado que el estudiante mantiene la carga académica y cobertura regular del periodo lectivo.

- **Práctica Estival (`internship_period`: "Verano" o "Invierno"):** El seguro escolar es **estrictamente obligatorio**. No se permitirá el registro de ninguna práctica estival que no cuente con la declaración explícita de cobertura de seguro.

  > **Excepción Administrativa:** Contemplada para ser implementada en el **Sprint 9** (gestión de casos excepcionales por secretaría de estudios o dirección de carrera).

### Base Legal y Contexto Institucional

- **Decreto Supremo N° 313:** Incluye a los estudiantes en el Seguro Escolar contra Accidentes del Trabajo y Enfermedades Profesionales de forma regular durante el año académico.

- **Reglamento de Prácticas FICA:** Dispone que toda actividad realizada fuera del periodo académico ordinario (periodo estival) requiere una extensión explícita de la cobertura del seguro para resguardar la integridad del alumno y la responsabilidad de la institución.

---

### Excepción Administrativa 
 
- Cuando una práctica estival no cuenta con seguro escolar (`has_school_insurance = False`), un actor administrativo autorizado puede registrar una excepción justificada que habilita el trámite sin modificar la declaración original del estudiante.

#### Principio de invariante
 
- `has_school_insurance` **nunca se muta** por vía administrativa. El campo siempre refleja la realidad declarada por el estudiante. La excepción registra el desvío y habilita el flujo, pero no convierte `False` en `True` ni implica cumplimiento real del requisito.
 
#### Roles autorizados para otorgar la excepción
 
| Rol | Puede otorgar excepción (`grant_exception`) |
| :--- | :---: |
| Encargado de práctica | **Sí** |
| Director de carrera | **Sí** |
| Secretaria de Carrera | No |
| Estudiante | No |
 
#### Condición de disparo
 
La excepción solo es relevante cuando se cumplen **las tres condiciones simultáneamente**:
 
1. `internship_period` es `"Verano"` o `"Invierno"`.
2. `has_school_insurance = False`.
3. El actor intenta avanzar el flujo de la práctica (acción `approve`).
Si no se registró una excepción activa para la regla `school_insurance`, el sistema bloquea el avance con `409 Conflict`.
 
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

## Especificación Técnica (API Contract)

### Endpoint: `POST /internships`

#### Caso 1 — Rechazo: Práctica Estival sin Seguro (al aprobar)

La validación del seguro escolar no ocurre al crear la práctica, sino al momento de aprobarla (`POST /internships/{internship_id}/approve`). Si la práctica es estival y el estudiante no tiene seguro escolar ni una excepción registrada, el sistema bloquea el avance.

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

#### Caso 2 — Éxito: Práctica Semestral (Seguro No Requerido)

Permite el registro sin necesidad de contar con seguro escolar activo.

  **Respuesta:** `201 Created`

```json
{
  "org_name": "Empresa SA",
  "sector": "Tecnología",
  "address": "Av. Principal 123",
  "city": "Temuco",
  "supervisor_name": "Ana Pérez",
  "supervisor_profession": "Ingeniera Civil Informática",
  "supervisor_position": "Jefa de Proyectos",
  "supervisor_department": "Tecnología",
  "supervisor_email": "ana.perez@empresa.cl",
  "supervisor_phone": "+56987654321",
  "start_date": "2026-06-01",
  "end_date": "2026-08-31",
  "schedule": "08:00 - 17:00",
  "days": "Lunes a Viernes",
  "modality": "Presencial",
  "internship_address": "Av. Principal 123",
  "act_description": "Desarrollo de software backend",
  "ben_description": "Aplicar conocimientos académicos",
  "internship_period": "Semestre",
  "internship_type": "Práctica de Estudio I"
}
```

---

#### Caso 3 — Éxito: Práctica Estival con Seguro (Obligatorio Cumplido)

Permite el registro en periodo estival siempre que se declare explícitamente la posesión del seguro.

  **Respuesta:** `201 Created`

```json
{
  "org_name": "Empresa SA",
  "sector": "Tecnología",
  "address": "Av. Principal 123",
  "city": "Temuco",
  "supervisor_name": "Ana Pérez",
  "supervisor_profession": "Ingeniera Civil Informática",
  "supervisor_position": "Jefa de Proyectos",
  "supervisor_department": "Tecnología",
  "supervisor_email": "ana.perez@empresa.cl",
  "supervisor_phone": "+56987654321",
  "start_date": "2026-01-05",
  "end_date": "2026-02-07",
  "schedule": "08:00 - 17:00",
  "days": "Lunes a Viernes",
  "modality": "Presencial",
  "internship_address": "Av. Principal 123",
  "act_description": "Desarrollo de software backend",
  "ben_description": "Aplicar conocimientos académicos",
  "internship_period": "Verano",
  "internship_type": "Práctica de Estudio I"
}
```
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

### Definición de la Regla

- La validación se aplica **exclusivamente al momento de aprobación** (`approve`), no al registro inicial (`create_internship`).
- Si la práctica en aprobación es de tipo `Práctica de Estudio II`, el sistema verifica que el estudiante tenga al menos una `Práctica de Estudio I` con estado `Aprobada`.
- Si no existe dicha práctica I aprobada, se bloquea el avance con `409 Conflict`.
- El bloqueo puede omitirse mediante una excepción administrativa de tipo `"sequentiality"`.
- La creación de Práctica II se permite sin restricciones de secuencialidad. El estudiante puede registrar la práctica, pero no podrá avanzarla hasta cumplir la regla u obtener una excepción.

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
 
### Endpoint: `POST /internships/{internship_id}/approve` (con práctica estival sin seguro)
 
#### Caso 8 — Rechazo: Estival sin seguro ni excepción activa
 
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
  no al registro inicial (`create_internship`).
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
  no al registro inicial (`create_internship`).
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
