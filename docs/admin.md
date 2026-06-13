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

El módulo `admin` expone endpoints administrativos para el rol
`Encargado de practica`. La gestión del seguro escolar también admite al
`Director de carrera`.
Permite:

- ver resumen general del sistema;
- listar estudiantes y prácticas registradas;
- consultar el detalle administrativo de una práctica registrada;
- listar requisitos de práctica por estudiante;
- actualizar el estado de un requisito de práctica con trazabilidad básica;
- consultar y registrar el cumplimiento institucional del seguro escolar.

---

## Ámbito y responsabilidades

El módulo `admin` no modifica la entidad `Internship` ni su flujo de creación.
Su alcance se centra en lectura administrativa y gestión de:

- requisitos académicos de práctica (`StudentInternshipRequirement`);
- prerrequisitos institucionales (`StudentRegistrationRequirement`), como el
  seguro escolar.

Para el dashboard del coordinador, el contrato oficial acordado es usar el
módulo `admin`:

- `GET /admin/summary` para tarjetas/resumen.
- `GET /admin/internships` para la tabla principal.
- `GET /admin/internships?status=submitted|in_review|approved|rejected` para
  filtros de estado del dashboard.
- `GET /admin/internships/{internship_id}` para el detalle administrativo.

El frontend del dashboard coordinador no debería depender de fallback silencioso
hacia `/internships`. Los endpoints `/internships/{id}/approve`,
`/internships/{id}/reject` y `/internships/{id}/derive` siguen siendo los
endpoints de acciones del flujo de práctica mientras no existan wrappers
administrativos equivalentes bajo `/admin`.

Responsabilidades clave:

- agregaciones y listados administrativos del sistema;
- visibilidad de estudiantes y prácticas existentes;
- gestión de estados de requisitos de práctica académica.
- registro institucional del seguro escolar usado por la aprobación de
  prácticas estivales.

---

## Endpoints disponibles

Todos los endpoints requieren autenticación. La tabla indica los roles
autorizados para cada operación.

| Método | Ruta | Propósito | Rol |
| --- | --- | --- | --- |
| GET | `/admin/summary` | Resumen global del sistema | Encargado de practica |
| GET | `/admin/students` | Listado administrativo de estudiantes | Encargado de practica |
| GET | `/admin/internships` | Listado de prácticas registradas. Query opcional `status` | Encargado de practica |
| GET | `/admin/internships/{internship_id}` | Detalle administrativo de práctica | Encargado de practica |
| GET | `/admin/students/{student_id}/internship-requirements` | Listado de requisitos de práctica | Encargado de practica |
| PATCH | `/admin/students/{student_id}/internship-requirements/{requirement_id}/status` | Actualiza estado de requisito | Encargado de practica |
| GET | `/admin/students/{student_id}/registration-requirements` | Lista prerrequisitos institucionales | Encargado de practica, Director de carrera |
| PATCH | `/admin/students/{student_id}/registration-requirements/school-insurance` | Crea o actualiza el seguro escolar vigente | Encargado de practica, Director de carrera |

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

`GET /admin/internships` acepta el query opcional `status` con valores
normalizados para el dashboard:

- `submitted`: prácticas sin estado o con estado `Pendiente`.
- `in_review`: prácticas con estado `En revisión` o `En revisión DIRAE`.
- `approved`: prácticas con estado `Aprobada`.
- `rejected`: prácticas con estado `Rechazada` o `Reprobada`.

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
    "description": "La solicitud de práctica fue creada y se encuentra en revisión administrativa."
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

### Seguro escolar institucional

`AdminRegistrationRequirementItem`

```json
{
  "id": 8,
  "user_id": 1,
  "requirement": "school_insurance",
  "is_completed": true,
  "completed_at": "2026-06-12T18:30:00Z",
  "updated_by": 5
}
```

El endpoint de actualización recibe:

```json
{
  "is_completed": true
}
```

La operación es un `upsert`: crea el requisito si no existe y actualiza el
registro existente en llamadas posteriores. Al enviar `false`, se limpia
`completed_at`.

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

El seguro escolar no utiliza la matriz anterior. Es un prerrequisito
institucional booleano:

- `is_completed = true`: existe cobertura registrada.
- `is_completed = false`: no existe cobertura vigente registrada.
- solo bloquea la aprobación final de prácticas `Verano` o `Invierno`;
- no bloquea la creación de una solicitud en estado `Pendiente`;
- una excepción de práctica no cambia el valor institucional.

---

## Consideraciones operativas

- Todos los endpoints exigen autenticación.
- Los endpoints de seguro aceptan `Encargado de practica` y
  `Director de carrera`; los demás mantienen el rol indicado en la tabla.
- Si el requisito no existe para el estudiante indicado, se retorna `404`.
- El cambio de estado actualiza `status_updated_at` y `status_updated_by`.
- El `PATCH` de seguro retorna `404` si el usuario no existe o no posee rol
  `Estudiante`.
