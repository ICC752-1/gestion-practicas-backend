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

