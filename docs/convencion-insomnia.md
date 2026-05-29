# Convención mínima de Insomnia

Esta guía define lo mínimo que debe mantenerse para que las pruebas manuales de API sean útiles y fáciles de revisar. Insomnia complementa a `pytest` y Swagger; no los reemplaza.

## Ubicación

Cada módulo mantiene su colección junto a sus pruebas:

```text
gestion-practicas-backend/tests/modules/<modulo>/<modulo>_test.yaml
```

Ejemplos actuales:

- `gestion-practicas-backend/tests/modules/internships/internships_test.yaml`
- `gestion-practicas-backend/tests/modules/notifications/notifications_test.yaml`

Para módulos nuevos usar el mismo patrón: `auth_test.yaml`, `admin_test.yaml`, `documents_test.yaml`, `tracking_test.yaml`.

## Variables obligatorias

Usar variables de entorno de Insomnia. No hardcodear URLs ni tokens.

| Variable | Valor local sugerido | Uso |
| --- | --- | --- |
| `base_url` | `http://localhost:8000` | URL base de la API |
| `access_token` | generado por login | Token Bearer para endpoints protegidos |
| `test_email` | correo semilla | Usuario de prueba |
| `test_password` | contraseña semilla | Password de prueba |

Formato:

- URL: `{{ _.base_url }}/auth/login`
- Header: `Authorization: Bearer {{ _.access_token }}`

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
- `Setup`: login u otros requests auxiliares.

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
```

Mensaje sugerido:

```bash
git commit -m "test(<modulo>): actualizar colección Insomnia"
```

## Checklist de PR

- [ ] La colección del módulo existe o fue actualizada.
- [ ] Usa `{{ _.base_url }}` y no URLs hardcodeadas.
- [ ] Los endpoints protegidos usan `Authorization: Bearer {{ _.access_token }}`.
- [ ] Hay al menos un happy path y un error esperado para lo modificado.
- [ ] Los payloads coinciden con Swagger y los schemas Pydantic actuales.
- [ ] La colección YAML exportada está incluida en el commit cuando corresponde.
