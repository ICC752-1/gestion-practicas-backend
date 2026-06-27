<h1 align="center"><em>Gestión de Prácticas Backend</em></h1>

<div align="center">
  <p>
    <a href="https://python.org">
      <img src="https://img.shields.io/badge/Python-3.14+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
    </a>
    <a href="https://fastapi.tiangolo.com">
      <img src="https://img.shields.io/badge/FastAPI-0.136+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
    </a>
    <a href="https://www.postgresql.org">
      <img src="https://img.shields.io/badge/PostgreSQL-15-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
    </a>
    <a href="https://www.docker.com">
      <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker Compose">
    </a>
    <a href="https://github.com/astral-sh/uv">
      <img src="https://img.shields.io/badge/uv-Astral-2E71FF?style=for-the-badge" alt="uv">
    </a>
  </p>
</div>

## Descripción

Backend del sistema de gestión de prácticas. Expone una API REST construida con FastAPI para apoyar el flujo administrativo y académico de prácticas, incluyendo estudiantes, roles administrativos, solicitudes, documentos, evaluaciones, agenda, notificaciones y exportación de datos.

## Funcionalidades Principales

- Autenticación local y Google OAuth.
- Gestión de usuarios, roles y permisos.
- Solicitudes de práctica e inducción.
- Seguimiento, aprobación, rechazo, excepciones y cierre de prácticas.
- Gestión documental, paquetes DIRAE y exportación CSV.
- Generación de cartas de presentación.
- Agenda de entrevistas y presentaciones.
- Autoevaluación y evaluación de supervisor.
- Notificaciones persistentes y envío por SMTP.
- Portabilidad de datos.

## Requisitos

- Python 3.14+
- uv
- Docker y Docker Compose
- PostgreSQL, si la base de datos se ejecuta fuera de Docker
- LibreOffice, si se generan cartas PDF fuera del contenedor

## Ejecución con Docker Compose

La forma principal de levantar el backend en local es usando Docker Compose, ya que inicia la API y PostgreSQL con la configuración del proyecto.

```bash
cp .env.example .env
docker compose up -d --build
```

Este comando inicia:

- Backend: `http://localhost:8000`
- PostgreSQL: `localhost:5432`

Para detener los servicios:

```bash
docker compose down
```

## Ejecución Local con PostgreSQL en Docker

Esta alternativa permite ejecutar el backend directamente con `uv`, manteniendo PostgreSQL en Docker.

```bash
cp .env.example .env
uv sync --dev
docker compose up -d --build db
uv run uvicorn app.main:app --reload
```

Cuando el backend se ejecuta fuera de Docker y la base de datos se levanta con Docker Compose, `POSTGRES_HOST` debe apuntar a `localhost` en el archivo `.env`.

## Probar en Local

Con el backend iniciado, los recursos locales quedan disponibles en:

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- PostgreSQL Docker: `localhost:5432`

Swagger UI es la vía recomendada para explorar y probar los endpoints disponibles durante el desarrollo local.

## Documentación

La documentación técnica y funcional del backend se mantiene en el repositorio de documentación del proyecto: `gestion-practicas-docs`.

Ahí se documentan los módulos de autenticación, prácticas, documentos, notificaciones, administración, agenda, cartas de presentación, autoevaluaciones, evaluaciones de supervisor, portabilidad de datos y estrategia de tests backend.
