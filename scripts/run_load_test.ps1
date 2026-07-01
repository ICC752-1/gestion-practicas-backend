param(
    [string]$BaseUrl = "http://localhost:8000",
    [ValidateRange(1, 500)]
    [int]$MaxVirtualUsers = 20,
    [switch]$Smoke
)

$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$testScript = Join-Path $repositoryRoot "tests\load\admin_dashboard.js"
$reportsDirectory = Join-Path $repositoryRoot "reports\k6"
$htmlReport = Join-Path $reportsDirectory "admin-dashboard.html"
$jsonReport = Join-Path $reportsDirectory "admin-dashboard-summary.json"

if (-not (Get-Command k6 -ErrorAction SilentlyContinue)) {
    throw "k6 no está instalado o no se encuentra en PATH."
}

if (
    -not $env:LOAD_TEST_TOKEN -and
    (-not $env:LOAD_TEST_EMAIL -or -not $env:LOAD_TEST_PASSWORD)
) {
    throw @"
Configure credenciales antes de ejecutar:
  `$env:LOAD_TEST_EMAIL='cuenta-demo'
  `$env:LOAD_TEST_PASSWORD='contraseña-demo'

Como alternativa, defina LOAD_TEST_TOKEN con un access token vigente.
"@
}

New-Item -ItemType Directory -Path $reportsDirectory -Force | Out-Null

$previousValues = @{
    LOAD_TEST_BASE_URL = $env:LOAD_TEST_BASE_URL
    LOAD_TEST_MAX_VUS = $env:LOAD_TEST_MAX_VUS
    LOAD_TEST_SMOKE = $env:LOAD_TEST_SMOKE
    K6_WEB_DASHBOARD = $env:K6_WEB_DASHBOARD
    K6_WEB_DASHBOARD_PORT = $env:K6_WEB_DASHBOARD_PORT
    K6_WEB_DASHBOARD_PERIOD = $env:K6_WEB_DASHBOARD_PERIOD
    K6_WEB_DASHBOARD_EXPORT = $env:K6_WEB_DASHBOARD_EXPORT
}

try {
    $env:LOAD_TEST_BASE_URL = $BaseUrl.TrimEnd("/")
    $env:LOAD_TEST_MAX_VUS = $MaxVirtualUsers.ToString()
    $env:LOAD_TEST_SMOKE = if ($Smoke) { "true" } else { "false" }
    $env:K6_WEB_DASHBOARD = "true"
    $env:K6_WEB_DASHBOARD_PORT = "-1"
    $env:K6_WEB_DASHBOARD_PERIOD = if ($Smoke) { "1s" } else { "10s" }
    $env:K6_WEB_DASHBOARD_EXPORT = $htmlReport

    & k6 run $testScript --summary-export $jsonReport
    if ($LASTEXITCODE -ne 0) {
        throw "La prueba k6 no cumplió sus verificaciones o umbrales."
    }

    if (Test-Path -LiteralPath $htmlReport) {
        Write-Output "Informe HTML: $htmlReport"
    }
    Write-Output "Resumen JSON: $jsonReport"
}
finally {
    foreach ($entry in $previousValues.GetEnumerator()) {
        Set-Item -Path "Env:$($entry.Key)" -Value $entry.Value
    }
}
