# Contratos backend Sprint 8

Este documento funciona como indice de contratos HTTP backend para la tarea 8.2.
No reemplaza la documentacion especifica de cada modulo; centraliza rutas activas
y referencia las fuentes de verdad existentes.

## Fuentes relacionadas

- `docs/admin.md`: contrato oficial de endpoints `/admin/*`.
- `docs/business_rules.md`: regla de seguro escolar para creación y aprobación
  de prácticas.
- Swagger/OpenAPI local: disponible al levantar FastAPI y consultar `/docs` o `/openapi.json`.

## Autenticacion

| Metodo | Ruta | Acceso | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/auth/login` | Publico | `OAuth2PasswordRequestForm` | `TokenResponse` |
| POST | `/auth/refresh` | Publico | `RefreshTokenRequest` o cookie HttpOnly | `TokenResponse` |
| GET | `/auth/me` | Bearer token | Header `Authorization` | `CurrentUserResponse` |
| POST | `/auth/logout` | Bearer token | `LogoutRequest` opcional o cookie HttpOnly | `204 No Content` |
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
REFRESH_TOKEN_COOKIE_NAME=refresh_token
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

- Exito: redireccion a `GOOGLE_FRONTEND_SUCCESS_URL?token=<access_token>` y
  cookie `refresh_token` `HttpOnly` para renovacion de sesion.
- Error: redireccion a `GOOGLE_FRONTEND_ERROR_URL?error=<codigo>`.

`POST /auth/refresh` acepta el `refresh_token` en body para login tradicional
o desde la cookie `HttpOnly` usada por OAuth. Al renovar, rota el refresh token
y actualiza la cookie. `POST /auth/logout` revoca el refresh token enviado o el
presente en la cookie, y elimina la cookie del navegador.

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

`POST /auth/login` usa `application/x-www-form-urlencoded`, no JSON. El campo
`username` corresponde al email del usuario:

```text
username=claudio.navarro@ufrontera.cl
password=my_secure_password
```

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

El dashboard del coordinador debe consumir el contrato administrativo oficial
del modulo `admin`: `GET /admin/summary`, `GET /admin/internships` y
`GET /admin/internships/{internship_id}`. El listado del estudiante autenticado
sigue siendo `GET /internships/me`. Las acciones de flujo de práctica
(`approve`, `reject`, `derive`) permanecen bajo `/internships/{id}/...` porque
modifican el estado de la entidad `Internship`.

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

### Creación y duplicidad por tipo

`POST /internships` crea una solicitud en estado `Pendiente` y activa
`blocks_new_registration=true`. Antes de persistir, y también mediante un índice
único parcial en base de datos, se impide crear otra solicitud vigente para el
mismo `user_id + internship_type`.

Bloquean nuevas solicitudes las prácticas con `blocks_new_registration=true`.
El bloqueo se libera al rechazar o anular la solicitud.

**Error de duplicidad (`409 Conflict`):**

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

### Acciones Administrativas (Flujo de Estados)

Para conocer la matriz de transiciones detallada y las reglas de negocio que evitan el flujo secuencial obligatorio, revisar **`docs/business_rules.md` (RN-02)**.

## Agenda de entrevistas y presentaciones

La primera parte de la agenda se expone bajo `/scheduling`. Reutiliza la tabla
`Presentation` como fuente de verdad para evitar duplicar citas en estructuras
paralelas.

| Metodo | Ruta | Acceso | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/scheduling/availability` | `Encargado de practica` o `Director de carrera` | `AvailabilityCreateRequest` | `list[PresentationSlotResponse]` |
| GET | `/scheduling/slots` | Bearer token | Query opcional `date_from`, `date_to`, `purpose` | `list[PresentationSlotResponse]` |
| GET | `/scheduling/appointments` | Bearer token | - | `list[PresentationSlotResponse]` |
| POST | `/scheduling/slots/{slot_id}/reserve` | `Estudiante` | `SlotReserveRequest` | `PresentationSlotResponse` |
| POST | `/scheduling/appointments/{appointment_id}/reschedule` | `Estudiante` propietario | `AppointmentRescheduleRequest` | `PresentationSlotResponse` |
| POST | `/scheduling/appointments/{appointment_id}/cancel` | Estudiante propietario o administrativo dueño del bloque | `AppointmentCancelRequest` | `PresentationSlotResponse` |
| POST | `/scheduling/availability/{slot_id}/close` | Administrativo dueño del bloque | `AppointmentCancelRequest` | `PresentationSlotResponse` |

`POST /scheduling/availability` recibe una fecha, rango horario y duración en
minutos; el backend genera bloques consecutivos futuros y rechaza solapamientos
del administrativo. Los propósitos iniciales son `initial_interview` y
`final_presentation`.

`POST /scheduling/slots/{slot_id}/reserve` solo permite reservar para una
práctica propia, no anulada y sin cita activa duplicada para el mismo propósito.
La reserva se resuelve con bloqueo de fila y responde `409 Conflict` si el slot
ya no está disponible, si existe solapamiento del estudiante o si la práctica ya
tiene una cita vigente de ese propósito.

La cancelación administrativa exige motivo. La cancelación del estudiante no lo
exige en esta primera parte.

#### Aprobación (`POST /internships/{internship_id}/approve`)

* **Payload (`InternshipActionRequest`):**

```json
{
  "comment": "Comentario opcional de aprobación"
}
```

**Comportamiento Dinámico:** Si la práctica está **Pendiente**, el rol de **Director** la avanzará directamente a **Aprobada**. El rol de **Encargado** la avanzará a **En revisión**.

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
 
- `rule`: valores permitidos: `"school_insurance"`, `"sequentiality"`, `"sequentiality_thesis"`, `"parallel_course"`.
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
 
### Elegibilidad para formalizar una solicitud de práctica

`GET /internships/registration-eligibility` retorna el estado de los
prerrequisitos del estudiante autenticado. Acepta los queries opcionales:

- `internship_period`: `Semestre`, `Verano` o `Invierno`.
- `internship_type`: tipo de práctica.

La ausencia de seguro solo activa `blocked` cuando el periodo consultado es
`Verano` o `Invierno`. La inducción aprobada habilita la creación de la
solicitud; si `has_induction=false`, `can_create_request=false`. Si la versión
activa de inducción tiene `requires_retake=true`, solo un intento aprobado de
esa versión satisface el requisito.

**Respuesta (`RegistrationEligibilityResponse`):**

```json
{
  "has_school_insurance": true,
  "has_induction": true,
  "requires_retake": false,
  "has_school_insurance_exception": false,
  "has_approved_practice_1": false,
  "sequentiality_blocked": true,
  "has_sequentiality_exception": false,
  "has_blocking_internship": false,
  "blocking_internship_id": null,
  "blocking_internship_status": null,
  "can_create_request": true,
  "blocked": false,
  "next_step": "Puede crear la solicitud y continuar con su revisión administrativa."
}
```

Los campos `has_approved_practice_1`, `sequentiality_blocked` y
`has_sequentiality_exception` son informativos. `blocked` describe impedimentos
para creación, aprobación o formalización según la regla consultada.

Cuando se consulta con `internship_type`, el backend informa si ya existe una
solicitud bloqueante del mismo tipo. En ese caso `can_create_request=false` y el
frontend debe impedir el envío, ofreciendo navegación al detalle existente.

### Inducción obligatoria

`GET /internships/induction` retorna la versión activa publicada. Las preguntas
exponen alternativas como objeto estable `{clave: texto}` y el frontend debe
enviar la clave seleccionada:

```json
{
  "id": 1,
  "title": "Induccion obligatoria demo",
  "requires_retake": false,
  "min_score": 1,
  "questions": [
    {
      "id": 1,
      "question_text": "Confirma que revisaste la induccion obligatoria antes de tramitar tu practica.",
      "options": {
        "accept": "Entiendo y acepto",
        "reject": "No acepto"
      },
      "order": 1
    }
  ]
}
```

`POST /internships/induction/attempts`:

```json
{
  "answers": {
    "1": "accept"
  }
}
```

---

#### Errores Comunes de Flujo
 
| Código | Condición | Ejemplo de `detail` |
| --- | --- | --- |
| `400` | Comentario obligatorio ausente | `"El motivo/comentario es obligatorio para la acción: reject"` |
| `400` | Regla no exceptuable | `"La regla 'x' no admite excepción administrativa."` |
| `403` | Rol sin permisos | `"Insufficient permissions"` |
| `404` | Práctica no existe | `"Práctica no encontrada (Internship not found)"` |
| `409` | Estado terminal | `"No se puede operar sobre una práctica en estado terminal: Aprobada."` |
| `409` | Creación sin inducción aprobada | `{"code": "induction_required", "message": "Debe aprobar la inducción obligatoria antes de crear una solicitud de práctica."}` |
| `409` | Práctica I sin inducción aprobada | `"La inducción es un requisito absoluto e inexceptuable para la Práctica de Estudio I. ..."` |
| `409` | Estival sin seguro ni excepción | `{"rule": "school_insurance", "message": "..."}` |
| `409` | Solicitud duplicada por tipo de práctica | `{"code": "duplicate_internship_type", "existing_internship_id": 15, "internship_type": "Práctica de Estudio I", "existing_status": "Pendiente", "message": "..."}` |
| `409` | Secuencialidad: Práctica II sin Práctica I aprobada ni excepción | `{"rule": "sequentiality", "message": "La Práctica de Estudio II requiere que la Práctica de Estudio I se encuentre aprobada. ..."}` |
| `409` | Secuencialidad: Tesis sin Práctica II aprobada ni excepción | `{"rule": "sequentiality_thesis", "message": "La Tesis requiere que la Práctica de Estudio II se encuentre aprobada. ..."}` |
| `409` | Paralelo: Práctica Controlada sin excepción de ramo en paralelo | `{"rule": "parallel_course", "message": "La Práctica Controlada requiere que los co-requisitos estén resueltos. ..."}` |

---

### Dashboard coordinador

Fuente oficial para 10.17:

- `GET /admin/summary`: tarjetas/resumen del dashboard.
- `GET /admin/internships`: tabla principal de prácticas.
- `GET /admin/internships/{internship_id}`: detalle administrativo.

Filtros validos para `GET /admin/internships?status=`:

- `submitted`: practicas sin estado o con estado `Pendiente`.
- `in_review`: practicas con estado `En revisión` o `En revisión DIRAE`.
- `approved`: practicas con estado `Aprobada`.
- `rejected`: practicas con estado `Rechazada` o `Reprobada`.

El frontend no debe usar fallback silencioso desde `/admin/*` hacia
`/internships` para el dashboard coordinador. Si `/admin/*` retorna `403`, el
problema es de permisos/rol y debe mostrarse como error.

### Seguro escolar institucional

| Método | Ruta | Acceso | Request | Response |
| --- | --- | --- | --- | --- |
| `GET` | `/admin/students/{student_id}/registration-requirements` | Encargado de practica, Director de carrera | - | `list[AdminRegistrationRequirementItem]` |
| `PATCH` | `/admin/students/{student_id}/registration-requirements/school-insurance` | Encargado de practica, Director de carrera | `AdminUpdateSchoolInsuranceRequest` | `AdminRegistrationRequirementItem` |

Request:

```json
{
  "is_completed": true
}
```

Respuesta:

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

El `PATCH` crea o actualiza el registro institucional. Esta operación no otorga
una excepción y no aprueba automáticamente ninguna práctica.

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
    "reason": "Creación inicial de solicitud de práctica",
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
  "internship_type": "Práctica de Estudio I"
}
```

Valores validos relevantes:

- `modality`: `Presencial`, `Remoto`, `Híbrido`.
- `internship_period`: `Semestre`, `Verano`, `Invierno`.
- `internship_type`: `Práctica de Estudio I`, `Práctica de Estudio II`, `Práctica Controlada`, `Tesis`.
- `has_school_insurance` no se envía en `POST /internships`; el backend genera
  una copia de compatibilidad desde el prerrequisito institucional. La
  aprobación final vuelve a consultar el requisito vigente. Una excepción no
  convierte este valor en `true`.

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
`internship_period` e `internship_type`. Para mostrar advertencias contextuales
de seguro e inducción, consultar
`GET /internships/registration-eligibility?internship_period=...&internship_type=...`.
La respuesta debe usarse para impedir el acceso al formulario cuando
`has_induction=false` o `can_create_request=false`. El backend mantiene la
validación autoritativa en `POST /internships`.

## Documentos

El modulo `documents` centraliza la carga y revision de archivos asociados a
practicas. Los archivos se guardan en storage privado local y nunca se exponen
como URL publica; toda descarga pasa por endpoint autenticado.

La politica de almacenamiento, privacidad, retencion y operacion en VPS se
documenta en `docs/documents-privacy.md`.

| Metodo | Ruta | Acceso | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/documents/types` | Bearer token | - | `list[DocumentTypeResponse]` |
| POST | `/internships/{internship_id}/documents` | Estudiante propietario | `multipart/form-data` con `document_type_id` y `file` | `DocumentResponse` |
| GET | `/internships/{internship_id}/documents` | Propietario o rol documental | Path `internship_id` | `list[DocumentResponse]` |
| GET | `/internships/{internship_id}/documents/package` | Propietario o rol documental | Path `internship_id` | `DocumentPackageResponse` |
| GET | `/documents/{document_id}/download` | Propietario o rol documental | Path `document_id` | Archivo binario |
| PATCH | `/documents/{document_id}/status` | Rol documental | `DocumentStatusUpdateRequest` | `DocumentResponse` |
| DELETE | `/documents/{document_id}` | Propietario si no esta aprobado, o rol documental | Path `document_id` | `204 No Content` |
| GET | `/dirae/document-packages/export` | Rol documental | Query opcional `internship_ids` repetible | CSV `text/csv` |

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

### DIRAE / Paquete documental

`GET /internships/{internship_id}/documents/package` calcula el paquete
documental de una practica. Puede consultarlo el estudiante propietario o un
rol documental autorizado. La respuesta indica si la practica es exportable a
DIRAE sin crear lotes persistidos.

Reglas de exportabilidad:

- la practica debe estar en estado `Aprobada`;
- cada `DocumentType` activo con `is_required = true` debe tener un documento
  `approved` no eliminado;
- si existe mas de un documento aprobado para el mismo tipo, se usa el mas
  reciente por `upload_date DESC, id DESC`;
- `reasons` usa valores estables: `internship_not_approved` y
  `missing_required_documents`.

Respuesta resumida:

```json
{
  "internship_id": 7,
  "status": "Aprobada",
  "exportable": true,
  "reasons": [],
  "student": {
    "id": 10,
    "rut": "12.345.678-9",
    "enrollment": "12345678923",
    "first_name": "Juan",
    "last_name": "Perez",
    "email": "juan.perez@correo.cl",
    "degree": "Ingenieria Civil Informatica",
    "cod_degree": "INF-001"
  },
  "internship": {
    "type": "Práctica de Estudio I",
    "period": "Semestre",
    "organization": "Empresa Demo SpA",
    "city": "Temuco",
    "start_date": "2026-06-01",
    "end_date": "2026-08-31"
  },
  "required_documents": [
    {
      "type_id": 1,
      "type_name": "Formulario de inscripción",
      "status": "approved",
      "document": {
        "id": 15,
        "file_name": "formulario.pdf",
        "extension": "pdf",
        "status": "approved"
      }
    }
  ],
  "optional_documents": []
}
```

`GET /dirae/document-packages/export` exporta CSV con:

```text
internship_id,student_id,student_rut,student_enrollment,student_first_name,student_last_name,student_email,degree,cod_degree,internship_type,internship_period,organization,city,start_date,end_date,approved_document_ids,required_document_type_ids,exported_at
```

`student_enrollment` se calcula como RUT sin puntos ni guion más los dos últimos
dígitos del año de ingreso cuando ese dato está disponible en el usuario. Si el
año de ingreso todavía no existe en el modelo de datos, el campo se retorna vacío
en CSV y `null` en el paquete JSON.

El query `internship_ids` es opcional y repetible:

```text
/dirae/document-packages/export?internship_ids=1&internship_ids=2
```

Si se omite, exporta todas las practicas aprobadas y exportables. Si no hay
filas exportables, responde `200 OK` con solo el encabezado CSV. La respuesta
incluye `Content-Disposition` con nombre
`dirae_document_packages_YYYYMMDD_HHMMSS.csv`.

La exportación define el evento interno `dirae_export_generated` con actor,
fecha, prácticas, documentos, archivo y resultado de generación para integración
posterior con auditoría. En el MVP no se persiste un lote DIRAE propio ni se
envía el archivo a sistemas externos.

Errores esperados:

- `400 Bad Request`: extension invalida, archivo vacio, tamano excedido o
  observacion sin comentario.
- `403 Forbidden`: acceso cruzado o rol insuficiente.
- `404 Not Found`: practica, tipo documental, documento o archivo inexistente.
- `409 Conflict`: carga en practica terminal o estudiante intentando eliminar
  un documento aprobado.
- `409 Conflict`: exportacion DIRAE solicitada explicitamente para una practica
  no exportable.
