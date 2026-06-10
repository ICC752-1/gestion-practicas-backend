# Convención mínima de Insomnia

Esta guía define lo mínimo que debe mantenerse para que las pruebas manuales de API sean útiles y fáciles de revisar. Insomnia complementa a `pytest` y Swagger; no los reemplaza.

## Ubicación

Cada módulo mantiene su colección junto a sus pruebas:

```text
gestion-practicas-backend/tests/modules/<modulo>/<modulo>_test.yaml
```

Ejemplos actuales:

- `gestion-practicas-backend/tests/modules/internships/internships_test.yaml`
- `gestion-practicas-backend/tests/modules/auth/auth_endpoints_test.yaml`
- `gestion-practicas-backend/tests/modules/documents/documents_test.yaml`

Para módulos nuevos usar el mismo patrón: `auth_test.yaml`, `admin_test.yaml`, `documents_test.yaml`, `tracking_test.yaml`.

## Variables obligatorias

Usar variables de entorno de Insomnia. No hardcodear URLs ni tokens. La
colección YAML debe incluir el bloque `environments:` con estas variables para
que Insomnia las cree automáticamente al importar el archivo.

| Variable | Valor local sugerido | Uso |
| --- | --- | --- |
| `base_url` | `http://localhost:8000` | URL base de la API |
| `access_token` | generado por login | Token Bearer para endpoints protegidos |
| `refresh_token` | generado por login | Token para refresh/logout cuando aplique |
| `test_email` | correo semilla | Usuario de prueba |
| `test_password` | contraseña semilla | Password de prueba |

Formato:

- URL: `{{ _.base_url }}/auth/login`
- Header: `Authorization: Bearer {{ _.access_token }}`
- Header con token por rol: `Authorization: Bearer {{ _.student_access_token }}`

Si el módulo usa variables adicionales, también deben declararse en
`environments.data`. Ejemplos: `student_access_token`, `director_access_token`,
`student_refresh_token`, `director_refresh_token`, `internship_id`,
`document_type_id`, `document_id`, `document_fixture_path`. Los tokens pueden
quedar vacíos o como placeholders; no guardar tokens reales ni secretos
personales en el YAML.

## Estructura de colección

Mantener una colección por módulo con esta estructura simple:

```text
<Modulo> API
├── Happy path
├── Errores esperados
└── Setup
```

- `Happy path`: requests exitosos principales.
- `Errores esperados`: al menos un caso relevante por endpoint modificado.
- `Setup`: login u otros requests auxiliares, incluida la creación por API de
  recursos previos necesarios para el happy path.

Si una prueba necesita un recurso transaccional, por ejemplo una práctica para
probar documentos, preferir crearlo en `Setup` con el endpoint público
correspondiente y guardar su `id` en el environment. Reservar `init.sql` para
catálogos, roles, usuarios semilla y datos base estables.

Cuando un request genera tokens o IDs que se usan en pasos posteriores, agregar
un `scripts.afterResponse` para actualizar el environment. No dejar como paso
manual "copiar el token" si Insomnia puede guardarlo automáticamente.

Para login simple:

```yaml
scripts:
  afterResponse: |-
    const body = insomnia.response.json();

    if (body.access_token) {
      insomnia.environment.set("access_token", body.access_token);
    }
    if (body.refresh_token) {
      insomnia.environment.set("refresh_token", body.refresh_token);
    }
```

Para login por rol, guardar el token en una variable explícita del rol:

```yaml
scripts:
  afterResponse: |-
    const body = insomnia.response.json();

    if (body.access_token) {
      insomnia.environment.set("student_access_token", body.access_token);
    }
    if (body.refresh_token) {
      insomnia.environment.set("student_refresh_token", body.refresh_token);
    }
```

Para IDs generados por requests de setup:

```yaml
scripts:
  afterResponse: |-
    const body = insomnia.response.json();

    if (body.id) {
      insomnia.environment.set("internship_id", body.id);
    }
```

Para requests `multipart/form-data` con archivos, incluir un fixture pequeño en
el repo, por ejemplo `tests/fixtures/<modulo>/archivo.pdf`, y declarar su ruta
en `environments.data` para que la colección importada quede autocontenida.

## Nombres de requests

Usar:

```text
<METODO> <recurso o acción>
```

Ejemplos:

- `POST Login`
- `GET Me`
- `POST Create Internship`
- `GET Admin Summary`
- `PATCH Update Requirement Status`

Para errores:

- `GET Me (sin token)`
- `POST Login (credenciales invalidas)`
- `POST Create Internship (payload invalido)`
- `GET Admin Summary (rol incorrecto)`

## Casos mínimos por endpoint nuevo o modificado

Antes de cerrar una tarea backend, la colección debe probar:

- Un happy path con status code esperado.
- Un caso sin token si el endpoint es protegido.
- Un caso de permiso incorrecto si depende de rol.
- Un caso de payload inválido si recibe body.
- Un caso `404` si consulta un recurso por id.

No es necesario documentar todos los casos posibles en Insomnia; los casos exhaustivos van en `pytest`.

## Exportación

Después de modificar una colección:

1. Exportar como colección de Insomnia en formato **YAML**.
2. Guardar en `tests/modules/<modulo>/<modulo>_test.yaml`.
3. Incluir el archivo en el commit si el endpoint cambió.

El encabezado esperado es el que genera Insomnia para colecciones YAML, por ejemplo:

```yaml
type: collection.insomnia.rest/5.0
schema_version: "5.1"
name: <Modulo> API tests
meta:
  id: wrk_<modulo>_api_tests
  created: 1778800000000
  modified: 1778800000000
  description: ""
collection:
  - name: Setup
    children: []
cookieJar:
  name: Default Jar
  meta:
    id: jar_<modulo>_api_tests
    created: 1778800000001
    modified: 1778800000001
environments:
  name: Base Environment
  meta:
    id: env_<modulo>_api_tests
    created: 1778800000002
    modified: 1778800000002
    isPrivate: false
  data:
    base_url: http://127.0.0.1:8000
    test_email: usuario.semilla@ejemplo.cl
    test_password: my_secure_password
    access_token: paste_access_token_here
    refresh_token: paste_refresh_token_here
```

La raíz del archivo debe ser un **mapa YAML** con la clave `collection:`. No usar
formatos abreviados o antiguos como:

```yaml
type: insomnia.rest
specName: Gestion Practicas
__ dangerouslyForceUpdate: true

- request:
    name: GET Example
```

Ese formato mezcla claves de mapa con una lista raíz y puede fallar al importar
con errores como `A block sequence may not be used as an implicit map key`.
Tampoco usar claves con espacios como `__ dangerouslyForceUpdate`; si Insomnia
exporta metadatos internos, deben conservarse solo si son YAML válido generado
por la herramienta.

Mensaje sugerido:

```bash
git commit -m "test(<modulo>): actualizar colección Insomnia"
```

## Checklist de PR

- [ ] La colección del módulo existe o fue actualizada.
- [ ] Usa `{{ _.base_url }}` y no URLs hardcodeadas.
- [ ] Declara `environments.data` con todas las variables usadas por la colección.
- [ ] Los logins y requests de setup guardan tokens e IDs con `scripts.afterResponse`.
- [ ] Los endpoints protegidos usan `Authorization: Bearer {{ _.access_token }}` o la variable de token por rol correspondiente.
- [ ] Hay al menos un happy path y un error esperado para lo modificado.
- [ ] Los payloads coinciden con Swagger y los schemas Pydantic actuales.
- [ ] La colección YAML exportada está incluida en el commit cuando corresponde.
