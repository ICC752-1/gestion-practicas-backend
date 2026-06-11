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

## Especificación Técnica (API Contract)

### Endpoint: `POST /internships`

#### Caso 1 — Rechazo: Práctica Estival sin Seguro

Si se intenta registrar una práctica en periodo estival (`"Verano"` o `"Invierno"`) y sin seguro (`"has_school_insurance": false`), el sistema denegará la petición.

**Respuesta:** `400 Bad Request`

```json
{
  "detail": {
    "field": "has_school_insurance",
    "message": "No es posible registrar práctica estival sin respaldo de seguro escolar vigente (D.S. 313)"
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
  "internship_type": "Práctica de Estudio I",
  "has_school_insurance": false
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
  "start_date": "2026-06-01",
  "end_date": "2026-08-31",
  "schedule": "08:00 - 17:00",
  "days": "Lunes a Viernes",
  "modality": "Presencial",
  "internship_address": "Av. Principal 123",
  "act_description": "Desarrollo de software backend",
  "ben_description": "Aplicar conocimientos académicos",
  "internship_period": "Verano",
  "internship_type": "Práctica de Estudio I",
  "has_school_insurance": true
}
```

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

## RN-03: Gestión Documental por Propiedad, Rol y Estado

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

### Restricciones Técnicas

- Extensiones permitidas: `pdf`, `docx`, `jpg`, `png`, `zip`.
- Tamaño máximo inicial: `10485760` bytes por archivo.
- El campo `file_path` es una clave interna de storage privado y no debe
  exponerse en respuestas JSON.
- Las descargas siempre pasan por `GET /documents/{document_id}/download` con
  autenticación y autorización.

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
