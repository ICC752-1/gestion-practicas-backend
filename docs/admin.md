<h1 align="center"><em>Admin</em></h1>

> [!NOTE]
> Esta documentación describe el comportamiento actual del módulo `admin`.

## Contenidos
- [Resumen operativo](#resumen-operativo)
- [Ámbito y responsabilidades](#ámbito-y-responsabilidades)
- [Endpoints disponibles](#endpoints-disponibles)
- [Contratos principales](#contratos-principales)
- [Reglas de negocio](#reglas-de-negocio)
- [Consideraciones operativas](#consideraciones-operativas)

---

## Resumen operativo

El módulo `admin` expone endpoints administrativos para el rol `Encargado de practica`.
Permite:

- ver resumen general del sistema;
- listar estudiantes y prácticas registradas;
- consultar el detalle administrativo de una práctica registrada;
- listar requisitos de práctica por estudiante;
- actualizar el estado de un requisito de práctica con trazabilidad básica.

---

## Ámbito y responsabilidades

El módulo `admin` no modifica la entidad `Internship` ni su flujo de creación.
Su alcance se centra en lectura administrativa y gestión de requisitos de práctica
del estudiante (`StudentInternshipRequirement`).

Responsabilidades clave:

- agregaciones y listados administrativos del sistema;
- visibilidad de estudiantes y prácticas existentes;
- gestión de estados de requisitos de práctica académica.

---

## Endpoints disponibles

Todos los endpoints requieren autenticación y el rol `Encargado de practica`.

| Método | Ruta | Propósito | Rol |
| --- | --- | --- | --- |
| GET | `/admin/summary` | Resumen global del sistema | Encargado de practica |
| GET | `/admin/students` | Listado administrativo de estudiantes | Encargado de practica |
| GET | `/admin/internships` | Listado de prácticas registradas | Encargado de practica |
| GET | `/admin/internships/{internship_id}` | Detalle administrativo de práctica | Encargado de practica |
| GET | `/admin/students/{student_id}/internship-requirements` | Listado de requisitos de práctica | Encargado de practica |
| PATCH | `/admin/students/{student_id}/internship-requirements/{requirement_id}/status` | Actualiza estado de requisito | Encargado de practica |

---

## Contratos principales

### Resumen administrativo

`AdminSummaryResponse`

```json
{
  "total_students": 120,
  "total_internships": 45,
  "internships_by_status": [
    {"status": "Pendiente", "total": 10},
    {"status": "Aprobada", "total": 12}
  ]
}
```

### Estudiantes (listado)

`AdminStudentListItem`

```json
{
  "id": 1,
  "email": "student@correo.cl",
  "first_name": "Juan",
  "last_name": "Pérez",
  "rut": "12.345.678-9",
  "is_active": true
}
```

### Prácticas registradas

`AdminInternshipListItem`

```json
{
  "id": 15,
  "org_name": "Empresa X",
  "city": "Valdivia",
  "start_date": "2026-05-01",
  "end_date": "2026-07-30",
  "upload_date": "2026-04-15T10:00:00Z",
  "user_id": 1,
  "student": {
    "id": 1,
    "email": "student@correo.cl",
    "first_name": "Juan",
    "last_name": "Pérez",
    "rut": "12.345.678-9"
  },
  "status": {
    "id": 2,
    "title": "En revisión",
    "description": "La práctica fue registrada y se encuentra en revisión administrativa."
  }
}
```

### Requisitos de práctica por estudiante

`AdminStudentInternshipRequirementItem`

```json
{
  "id": 4,
  "user_id": 1,
  "type": "Práctica de Estudio I",
  "status": "Habilitada",
  "status_updated_at": "2026-05-28T14:10:00Z",
  "status_updated_by": 8,
  "created_at": "2026-05-20T09:00:00Z",
  "updated_at": "2026-05-28T14:10:00Z"
}
```

### Actualización de estado

`AdminUpdateStudentInternshipRequirementStatusRequest`

```json
{
  "status": "En revisión"
}
```

---

## Reglas de negocio

Estados posibles en requisitos de práctica:

- `Pendiente`
- `Habilitada`
- `En revisión`
- `Aprobada`
- `Rechazada`

Transiciones permitidas:

- `Pendiente` → `Habilitada`
- `Habilitada` → `En revisión`
- `En revisión` → `Aprobada`
- `En revisión` → `Rechazada`
- `Rechazada` → `Habilitada`

Las transiciones inválidas retornan error `400`.

---

## Consideraciones operativas

- Todos los endpoints exigen autenticación y rol `Encargado de practica`.
- Si el requisito no existe para el estudiante indicado, se retorna `404`.
- El cambio de estado actualiza `status_updated_at` y `status_updated_by`.
