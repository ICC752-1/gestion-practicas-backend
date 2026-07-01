# Pruebas de carga con k6

## Objetivo

Validar que las consultas administrativas principales mantengan tiempos de
respuesta aceptables y una tasa baja de errores bajo concurrencia controlada.

La prueba usa solamente operaciones de lectura:

- `GET /admin/summary`
- `GET /admin/internships`

No debe ejecutarse contra producción sin autorización. Use un entorno local o
de QA con datos semilla y una cuenta de `Encargado de practica`.

## Requisitos

- Backend y PostgreSQL iniciados.
- k6 disponible en `PATH`.
- Cuenta demo con permisos administrativos.

En Windows, k6 puede instalarse con:

```powershell
winget install k6 --source winget
```

## Configuración segura de credenciales

Defina las credenciales solamente como variables de entorno:

```powershell
$env:LOAD_TEST_EMAIL="encargado.practicas@ufrontera.cl"
$env:LOAD_TEST_PASSWORD="[contraseña-demo]"
```

También puede usar un access token vigente:

```powershell
$env:LOAD_TEST_TOKEN="[access-token]"
```

No agregue credenciales ni tokens al repositorio.

## Ejecución

Desde la raíz del backend:

```powershell
.\scripts\run_load_test.ps1
```

Para validar rápidamente credenciales, rutas e informes antes de la prueba:

```powershell
.\scripts\run_load_test.ps1 -Smoke
```

Para cambiar la URL o la carga máxima:

```powershell
.\scripts\run_load_test.ps1 `
  -BaseUrl "http://localhost:8000" `
  -MaxVirtualUsers 50
```

La prueba aumenta progresivamente hasta el máximo configurado y dura
aproximadamente 105 segundos.

## Criterios de aprobación

| Métrica | Umbral |
| --- | ---: |
| Solicitudes HTTP fallidas | Menor a 1% |
| Verificaciones aprobadas | Mayor a 99% |
| Percentil 95 de `/admin/summary` | Menor a 500 ms |
| Percentil 95 de `/admin/internships` | Menor a 800 ms |

Los umbrales son una línea base inicial. Deben ajustarse si existe un objetivo
institucional de rendimiento más específico.

## Evidencia

Cada ejecución genera archivos ignorados por Git:

- `reports/k6/admin-dashboard.html`
- `reports/k6/admin-dashboard-summary.json`

El informe HTML contiene las métricas y gráficos para incorporar como evidencia
en la presentación. El proceso devuelve un código distinto de cero cuando no se
cumplen los umbrales.
