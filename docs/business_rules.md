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
  "start_date": "2026-01-05",
  "end_date": "2026-02-07",
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