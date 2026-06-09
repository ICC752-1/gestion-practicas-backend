# Contratos backend Sprint 8

Este documento funciona como indice de contratos HTTP backend para la tarea 8.2.
No reemplaza la documentacion especifica de cada modulo; centraliza rutas activas
y referencia las fuentes de verdad existentes.

## Fuentes relacionadas

- `docs/admin.md`: contrato oficial de endpoints `/admin/*`.
- `docs/business_rules.md`: regla de seguro escolar para `POST /internships`.
- Swagger/OpenAPI local: disponible al levantar FastAPI y consultar `/docs` o `/openapi.json`.

## Autenticacion

| Metodo | Ruta | Acceso | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/auth/login` | Publico | `LoginRequest` | `TokenResponse` |
| GET | `/auth/me` | Bearer token | Header `Authorization` | `CurrentUserResponse` |
| POST | `/auth/logout` | Bearer token | `LogoutRequest` opcional | `204 No Content` |
| GET | `/auth/google/login` | Publico | - | `307 Redirect` a Google |
| GET | `/auth/google/callback` | Publico, callback Google | Query `code`, `state` | `303 Redirect` al frontend |

### Google OAuth institucional

`GET /auth/google/login` inicia el flujo OAuth de Google con scopes
`openid email profile`. El backend genera un `state` firmado y lo guarda en una
cookie `HttpOnly` para validar que el callback pertenezca al navegador que
inicio el login.

`GET /auth/google/callback` recibe el `code`, intercambia el codigo contra
Google, valida el `id_token`, verifica que el correo este confirmado y exige
que el dominio pertenezca a `GOOGLE_ALLOWED_DOMAINS`.

Variables sensibles requeridas:

```env
GOOGLE_CLIENT_ID=<client-id-web>
GOOGLE_CLIENT_SECRET=<client-secret-web>
```

Defaults locales no sensibles definidos por el backend:

```env
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
GOOGLE_ALLOWED_DOMAINS=ufromail.cl,ufrontera.cl
GOOGLE_FRONTEND_SUCCESS_URL=http://localhost:5173/auth/callback
GOOGLE_FRONTEND_ERROR_URL=http://localhost:5173/auth/callback
GOOGLE_COOKIE_SECURE=False
```

En produccion `GOOGLE_REDIRECT_URI` debe ser el callback HTTPS publico
registrado en Google Cloud, por ejemplo
`https://gestion-practicas-team-b.duckdns.org/api/auth/google/callback`, y
`GOOGLE_COOKIE_SECURE=True`.

En el despliegue Docker de produccion, `compose.prod.yml` define esos defaults
publicos de produccion. La `.env` del host solo necesita sobrescribirlos si
cambia el dominio o el callback autorizado.

Regla de usuario:

- Si existe un usuario activo con el correo Google validado, se reutiliza y sus
  roles actuales definen la navegacion del frontend.
- Si el dominio es permitido y no existe usuario, el backend crea un usuario
  activo y verificado con rol `Estudiante`.
- Como Google no entrega RUT, los usuarios creados por OAuth usan un RUT tecnico
  `google:<hash-del-sub>`. La password almacenada es aleatoria y no se expone,
  por lo que el acceso operativo de ese usuario queda ligado al OAuth.

Resultado hacia frontend:

- Exito: redireccion a `GOOGLE_FRONTEND_SUCCESS_URL?token=<access_token>`.
- Error: redireccion a `GOOGLE_FRONTEND_ERROR_URL?error=<codigo>`.

Codigos de error usados por el frontend:

- `unauthorized_domain`
- `invalid_callback`
- `missing_token`
- `server_unavailable`
- `user_not_found`

Limitaciones:

- Google exige que `GOOGLE_REDIRECT_URI` coincida exactamente con una URI
  autorizada en el cliente OAuth.
- Para pruebas locales, registrar
  `http://localhost:8000/auth/google/callback` en Google Cloud.
- En produccion, usar HTTPS publico; no registrar URLs internas de Docker ni
  callbacks sin TLS.

## Usuarios y roles

Estos routers estan registrados en la aplicacion FastAPI desde Sprint 8.2.
Todos requieren token y un rol administrativo permitido por el backend.

| Metodo | Ruta | Request | Response |
| --- | --- | --- | --- |
| POST | `/users` | `UserCreateRequest` | `UserResponse` |
| GET | `/users` | Query opcional `is_active`, `email` | `list[UserResponse]` |
| GET | `/users/{user_id}` | Path `user_id` | `UserResponse` |
| PATCH | `/users/{user_id}` | `UserUpdateRequest` | `UserResponse` |
| GET | `/users/{user_id}/roles` | Path `user_id` | `list[UserRoleResponse]` |
| POST | `/users/{user_id}/roles` | `AssignRoleRequest` | `UserRoleResponse` |
| DELETE | `/users/{user_id}/roles/{role_id}` | Path `user_id`, `role_id` | `204 No Content` |
| GET | `/roles` | - | `list[RoleResponse]` |
| GET | `/roles/{role_id}` | Path `role_id` | `RoleResponse` |
| PATCH | `/roles/{role_id}` | `RoleUpdateRequest` | `RoleResponse` |

## Practicas

`GET /internships` existe solo para el dashboard de coordinador/director. El
listado del estudiante autenticado sigue siendo `GET /internships/me`. Los
listados administrativos del modulo `admin` estan en `/admin/internships` y se
documentan en `docs/admin.md`.

| Metodo | Ruta | Acceso | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/internships` | Rol `Estudiante` | `InternshipCreateRequest` | `InternshipResponse` |
| GET | `/internships` | Rol `Encargado de practica` o `Director de carrera` | Query opcional `status` | `list[InternshipDashboardListItem]` |
| GET | `/internships/stats` | Rol `Encargado de practica` o `Director de carrera` | - | `InternshipDashboardStatsResponse` |
| GET | `/internships/me` | Bearer token | - | `list[InternshipResponse]` |
| GET | `/internships/{internship_id}/tracking` | Propietario o rol privilegiado | Path `internship_id` | `list[InternshipTrackingResponse]` |
| GET | `/internships/{internship_id}` | Propietario o rol privilegiado | Path `internship_id` | `InternshipResponse` |
| POST | `/internships/{internship_id}/approve` | Rol `Encargado de practica` o `Director de carrera` | `ApproveRequest` | `InternshipResponse` |
| POST | `/internships/{internship_id}/reject` | Rol `Encargado de practica` o `Director de carrera` | `RejectRequest` | `InternshipResponse` |
| POST | `/internships/{internship_id}/derive` | Rol `Secretaria de Carrera` | `DeriveRequest` | `InternshipResponse` |
| POST | `/internships/{internship_id}/exceptions` | Rol `Encargado de practica` o `Director de carrera` | `InternshipExceptionRequest` | `InternshipExceptionResponse` |
| GET | `/internships/{internship_id}/exceptions` | Propietario o rol privilegiado | Path `internship_id` | `list[InternshipExceptionResponse]` |

### Acciones Administrativas (Flujo de Estados)

Para conocer la matriz de transiciones detallada y las reglas de negocio que evitan el flujo secuencial obligatorio, revisar **`docs/business_rules.md` (RN-02)**.

#### Aprobación (`POST /internships/{internship_id}/approve`)

* **Payload (`ApproveRequest`):**

```json
{
  "comment": "Comentario opcional de aprobación",
  "skip_review": false
}
```

**Comportamiento Dinámico:** Si la práctica está **Pendiente**, el rol de **Director** o el flag `skip_review: true` la avanzará a **Aprobada**. El rol de **Encargado** (con `skip_review: false`) la avanzará a **En revisión**.

#### Rechazo (`POST /internships/{internship_id}/reject`)

* **Payload (`RejectRequest`):**

```json
{
  "comment": "Motivo explícito del rechazo"
}
```

**Restricción:** El campo `comment` es estrictamente obligatorio. Si se envía vacío, con espacios o nulo, la API responderá con un error **400 Bad Request**.

#### Derivación a DIRAE (`POST /internships/{internship_id}/derive`)

* **Payload (`DeriveRequest`):**

```json
{
  "comment": "Observaciones de la derivación documental"
}
```

**Restricción:** Acción exclusiva del rol **Secretaria de Carrera**. Exige comentario obligatorio.





#### Excepciones Administrativas (`POST /internships/{internship_id}/exceptions`)
 
Permite habilitar el trámite de una práctica cuando no se cumple una regla de negocio exceptuable (ej: seguro escolar en práctica estival, secuencialidad de prácticas). No modifica el campo que originó la validación; solo registra el desvío con trazabilidad completa.
 
Para la especificación completa de la regla ver **`docs/business_rules.md` (RN-01, Excepción Administrativa)**.
 
**Request (`InternshipExceptionRequest`):**
 
```json
{
  "rule": "school_insurance",
  "reason": "Póliza en proceso de firma. Documentación física recibida por Secretaría."
}
```
 
- `rule`: valores permitidos: `"school_insurance"`, `"sequentiality"`.
- `reason`: obligatorio, no puede estar vacío ni contener solo espacios.
**Respuesta exitosa** `201 Created` **(`InternshipExceptionResponse`):**
 
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
 
**Listado de excepciones** `GET /internships/{internship_id}/exceptions`:
 
Retorna `list[InternshipExceptionResponse]` ordenado por `authorized_at` ascendente. Accesible para el propietario de la práctica y roles privilegiados de lectura.
 
### Elegibilidad de registro

`GET /internships/eligibility` retorna el estado de los prerrequisitos del estudiante autenticado.

**Respuesta (`RegistrationEligibilityResponse`):**

```json
{
  "has_school_insurance": true,
  "has_induction": true,
  "has_school_insurance_exception": false,
  "has_approved_practice_1": false,
  "sequentiality_blocked": true,
  "has_sequentiality_exception": false,
  "blocked": false,
  "next_step": "Puede registrar una nueva práctica."
}
```

Los campos `has_approved_practice_1`, `sequentiality_blocked` y `has_sequentiality_exception` son informativos. El campo `blocked` no se activa por secuencialidad, solo por seguro escolar faltante o inducción no aprobada.

---

#### Errores Comunes de Flujo
 
| Código | Condición | Ejemplo de `detail` |
| --- | --- | --- |
| `400` | Comentario obligatorio ausente | `"El motivo/comentario es obligatorio para la acción: reject"` |
| `400` | Regla no exceptuable | `"La regla 'x' no admite excepción administrativa."` |
| `403` | Rol sin permisos | `"Insufficient permissions"` |
| `404` | Práctica no existe | `"Práctica no encontrada (Internship not found)"` |
| `409` | Estado terminal | `"No se puede operar sobre una práctica en estado terminal: Aprobada."` |
| `409` | Estival sin seguro ni excepción | `{"rule": "school_insurance", "message": "..."}` |
| `409` | Secuencialidad: Práctica II sin Práctica I aprobada ni excepción | `{"rule": "sequentiality", "message": "La Práctica de Estudio II requiere que la Práctica de Estudio I se encuentre aprobada. ..."}` |
 
---

### Dashboard coordinador

Filtros validos para `GET /internships?status=`:

- `submitted`: practicas sin estado o con estado `Pendiente`.
- `in_review`: practicas con estado `En revisión`.
- `approved`: practicas con estado `Aprobada`.
- `rejected`: practicas con estado `Rechazada` o `Reprobada`.

### Tracking de estados

`GET /internships/{internship_id}/tracking` retorna el historial cronologico de
estados de una practica. Puede consultarlo el estudiante propietario o un rol
privilegiado de lectura (`Encargado de practica`, `Director de carrera` o
`Secretaria de Carrera`).

Estados canonicos de practica:

- `Pendiente`
- `En revisión`
- `Aprobada`
- `Rechazada`

`Reprobada` se mantiene solo como compatibilidad de lectura para datos antiguos
y se interpreta como estado rechazado.

Respuesta resumida:

```json
[
  {
    "id": 1,
    "internship_id": 15,
    "previous_status": null,
    "new_status": {
      "id": 1,
      "title": "Pendiente",
      "description": "La práctica existe como estado del proceso."
    },
    "actor": {
      "id": 2,
      "email": "student@correo.cl",
      "first_name": "Juan",
      "last_name": "Perez"
    },
    "reason": "Registro inicial de práctica",
    "changed_at": "2026-06-03T10:30:00",
    "metadata": {
      "event": "internship_created"
    }
  }
]
```

Respuesta resumida:

```json
[
  {
    "id": 15,
    "org_name": "Empresa X",
    "city": "Temuco",
    "internship_type": "Práctica de Estudio I",
    "start_date": "2026-06-01",
    "end_date": "2026-08-31",
    "upload_date": "2026-05-29T12:00:00",
    "status": "submitted",
    "status_label": "Pendiente",
    "student": {
      "id": 1,
      "email": "student@correo.cl",
      "first_name": "Juan",
      "last_name": "Perez",
      "rut": "12.345.678-9",
      "degree": "Ingenieria Civil Informatica"
    }
  }
]
```

`GET /internships/stats` retorna:

```json
{
  "total": 12,
  "submitted": 4,
  "in_review": 3,
  "approved": 3,
  "rejected": 2
}
```

### Payload de creacion de practica

```json
{
  "org_name": "Empresa SA",
  "sector": "Tecnologia",
  "address": "Av. Principal 123",
  "city": "Temuco",
  "org_phone": "+56912345678",
  "web": "https://empresa.example",
  "supervisor_name": "Ana Perez",
  "supervisor_profession": "Ingeniera Civil Informatica",
  "supervisor_position": "Jefa de Proyectos",
  "supervisor_department": "Tecnologia",
  "supervisor_email": "ana.perez@empresa.example",
  "supervisor_phone": "+56987654321",
  "start_date": "2026-06-01",
  "end_date": "2026-08-31",
  "schedule": "09:00-18:00",
  "days": "Lunes a viernes",
  "modality": "Presencial",
  "internship_address": "Av. Practica 456",
  "act_description": "Desarrollo de funcionalidades backend.",
  "ben_description": "Bono locomocion y colacion.",
  "amount": 120000,
  "internship_period": "Semestre",
  "internship_type": "Práctica de Estudio I",
  "has_school_insurance": false
}
```

Valores validos relevantes:

- `modality`: `Presencial`, `Remoto`, `Híbrido`.
- `internship_period`: `Semestre`, `Verano`, `Invierno`.
- `internship_type`: `Práctica de Estudio I`, `Práctica de Estudio II`, `Práctica Controlada`, `Tesis`.
- `has_school_insurance`: obligatorio. Si el periodo es `Verano` o `Invierno`, debe ser `true`.

## Mapeo esperado desde formulario frontend

| Frontend | Backend |
| --- | --- |
| `organizationName` | `org_name` |
| `sector` | `sector` |
| `address` de organizacion | `address` |
| `city` | `city` |
| `phone` | `org_phone` |
| `website` | `web` |
| `supervisorName` | `supervisor_name` |
| `supervisorProfession` | `supervisor_profession` |
| `supervisorPosition` | `supervisor_position` |
| `supervisorDepartment` | `supervisor_department` |
| `supervisorEmail` | `supervisor_email` |
| `supervisorPhone` | `supervisor_phone` |
| `startDate` | `start_date` |
| `endDate` | `end_date` |
| `days[]` | `days` como texto consolidado |
| `startTime` + `endTime` | `schedule` |
| `practiceType` de modalidad | `modality` |
| direccion de practica | `internship_address` |
| `activities` | `act_description` |
| `benefits[]` | `ben_description` como texto consolidado |
| `paymentAmount` | `amount` |

Brechas frontend pendientes para FE1/8.6: capturar o derivar `city`,
`internship_period`, `internship_type` y `has_school_insurance`.

## Documentos

El modulo `documents` centraliza la carga y revision de archivos asociados a
practicas. Los archivos se guardan en storage privado local y nunca se exponen
como URL publica; toda descarga pasa por endpoint autenticado.

| Metodo | Ruta | Acceso | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/documents/types` | Bearer token | - | `list[DocumentTypeResponse]` |
| POST | `/internships/{internship_id}/documents` | Estudiante propietario | `multipart/form-data` con `document_type_id` y `file` | `DocumentResponse` |
| GET | `/internships/{internship_id}/documents` | Propietario o rol documental | Path `internship_id` | `list[DocumentResponse]` |
| GET | `/documents/{document_id}/download` | Propietario o rol documental | Path `document_id` | Archivo binario |
| PATCH | `/documents/{document_id}/status` | Rol documental | `DocumentStatusUpdateRequest` | `DocumentResponse` |
| DELETE | `/documents/{document_id}` | Propietario si no esta aprobado, o rol documental | Path `document_id` | `204 No Content` |

Roles documentales autorizados:

- `Encargado de practica`
- `Director de carrera`
- `Secretaria de Carrera`

### Carga documental

`POST /internships/{internship_id}/documents` usa `multipart/form-data`:

```text
document_type_id=1
file=<archivo>
```

Restricciones:

- extensiones permitidas: `pdf`, `docx`, `jpg`, `png`, `zip`;
- tamano maximo por defecto: `10485760` bytes;
- la practica debe existir y pertenecer al estudiante autenticado;
- no se permite cargar en practicas con estado terminal `Aprobada`, `Rechazada`
  o `Reprobada`.

### Revision documental

`PATCH /documents/{document_id}/status` acepta:

```json
{
  "status": "observed",
  "comment": "Falta firma del estudiante"
}
```

Valores validos:

- `observed`: exige `comment`.
- `approved`: permite `comment` opcional.

### Respuesta documental

`DocumentResponse` no incluye `file_path`, porque esa clave pertenece al storage
interno.

```json
{
  "id": 15,
  "file_name": "formulario.pdf",
  "extension": "pdf",
  "status": "uploaded",
  "size_bytes": 120440,
  "upload_date": "2026-06-09T10:00:00",
  "update_date": "2026-06-09T10:00:00",
  "internship_id": 7,
  "type_id": 1,
  "user_id": 3,
  "reviewed_at": null,
  "reviewed_by": null,
  "review_comment": null,
  "deleted_at": null,
  "deleted_by": null,
  "document_type": {
    "id": 1,
    "name": "Formulario de inscripción",
    "description": "Formulario de inscripción de práctica firmado o respaldado.",
    "is_required": true,
    "category": "Académico",
    "is_active": true
  }
}
```

Estados documentales:

- `uploaded`
- `observed`
- `approved`
- `deleted`

Errores esperados:

- `400 Bad Request`: extension invalida, archivo vacio, tamano excedido o
  observacion sin comentario.
- `403 Forbidden`: acceso cruzado o rol insuficiente.
- `404 Not Found`: practica, tipo documental, documento o archivo inexistente.
- `409 Conflict`: carga en practica terminal o estudiante intentando eliminar
  un documento aprobado.
