<div align="center">
  <h2><i>Gestión de Prácticas DCI</i></h2>
  <p>
    <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-0.136.1+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"></a>
    <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.14+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"></a>
    <a href="https://www.docker.com"><img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"></a>
    <a href="https://github.com/astral-sh/uv"><img src="https://img.shields.io/badge/uv-Astral-2E71FF?style=for-the-badge" alt="uv"></a>
    <a href="https://github.com/ICC752-1/gestion-practicas-backend/actions/workflows/ci.yml"><img src="https://github.com/ICC752-1/gestion-practicas-backend/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  </p>
  <p>
    <a href="#contexto">Contexto</a> ·
    <a href="#funcionalidades">Funcionalidades</a> ·
    <a href="#setup">Setup</a> ·
    <a href="#documentacion">Documentación</a> ·
    <a href="#endpoints-disponibles">Endpoints Disponibles</a> ·
  </p>
</div>

---
### Contexto 
Este repositorio contiene el backend del sistema de gestión del proceso de inscripción de práctica de estudios. Su objetivo es centralizar la lógica de negocio, la gestión de datos y la exposición de servicios API necesarios para apoyar el flujo administrativo entre estudiantes, encargados de práctica, directores de carrera, secretaría y otros actores involucrados.

El backend sigue una arquitectura monolito modular con separación por capas como patrón arquitectónico, lo cual permite organizar el sistema por módulos funcionales, mantener bajo acoplamiento entre componentes y facilitar su evolución conforme aumenten los requerimientos del proyecto.

---
### Funcionalidades
La siguiente tabla resume las capacidades principales consideradas en el
sistema propuesto.

> Leyenda de estado: ⬤ implementado, ◐ parcial, ◯ no implementado.

| Capacidad | Estado |
| --- | --- |
| Autenticación con emisión de tokens | ◐ |
| Consulta del usuario autenticado | ◐ |
| Gestión de estudiantes | ◯ |
| Gestión de prácticas | ◐ |
| Inicialización de base de datos con datos base | ⬤ |
| Validación de credenciales y estado de usuario | ◐ |
| Logging y auditoría de acciones | ◯ |

### Setup 
#### 1. Clonar el repositorio.

```bash
git clone git@github.com:ICC752-1/gestion-practicas-backend.git
cd gestion-practicas-backend
```

#### 2. Crear el archivo `.env` a partir de `.env.example`.

```bash
cp .env.example .env
```

> [!CAUTION]
> Antes de continuar, debes completar las variables de entorno del archivo `.env`.

#### 3. Levantar la base de datos con Docker Compose.

```bash
docker compose up -d --build db
```

#### 4. Abrir la documentación interactiva en:

```text
http://127.0.0.1:8000/docs
```

#### 5. Verificación local (lint + tests)

```bash
uv sync --dev
uv run ruff check .
uv run pytest --tb=short
```

### Documentación
Esta sección reúne documentación propia del funcionamiento interno del sistema.

> Para un alcance mayor y otros dominios, revise el repositorio de documentación.

- [Logging](docs/logging.md)

### CI/CD
El repositorio cuenta con workflows automatizados:

- **CI**: ejecuta lint y tests en cada push y pull request.
- **CD**: al hacer merge a `main` construye la imagen y despliega en la VPS.

La imagen de producción se publica en:

- `ghcr.io/icc752-1/gestion-practicas-backend:latest`
- `ghcr.io/icc752-1/gestion-practicas-backend:<commit_sha>`

#### Despliegue en producción
1. Crear la carpeta `/home/ci/gestion-practicas-backend` en la VPS.
2. Copiar `docker-compose.prod.yml` y `.env.production` a esa ruta.
3. Copiar `app/core/database/init.sql` a `/home/ci/gestion-practicas-backend/app/core/database/init.sql`.
4. Completar las variables de entorno en `.env.production`.
5. Ejecutar el despliegue con Docker Compose:

```bash
sudo docker compose -f docker-compose.prod.yml pull
sudo docker compose -f docker-compose.prod.yml up -d
```

> [!NOTE]
> La base de datos de producción persiste datos en el volumen `pgdata`.

#### Reproducir CI localmente
```bash
uv sync --dev
uv run ruff check .
uv run pytest --tb=short
```

### Notas de uso
- Para detener la base de datos:

```bash
docker compose down
```

- Para acceder al contenedor de PostgreSQL:

```bash
docker exec -it internship_db psql -U <usuario> -d internship_db
```

> [!NOTE] 
> El contenedor carga automáticamente `app/core/database/init.sql` al iniciar.

> [!NOTE]
> El script de inicialización inserta un usuario base para pruebas de autenticación.
> La contraseña asociada es `my_secure_password`.

### Endpoints disponibles
#### Autenticación

- `POST /auth/login`
- `GET /auth/me`
- `POST /auth/logout`

#### Gestión de prácticas

- `POST /internships`: crea una práctica asociada al estudiante autenticado. Requiere token Bearer y rol `Estudiante`.
- `GET /internships/me`: lista las prácticas registradas por el usuario autenticado.
- `GET /internships/{internship_id}`: obtiene el detalle de una práctica por identificador. Permite acceso al estudiante propietario o a roles con permisos de revisión.

> [!NOTE]
> La gestión de prácticas se encuentra en estado parcial: actualmente permite crear prácticas, listar las prácticas propias y consultar el detalle de una práctica existente. Aún quedan pendientes flujos como actualización de estado, revisión, aprobación/rechazo, documentos asociados e integración completa con los demás módulos del proceso.
