param(
    [switch]$SkipFullCycleTest
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repositoryRoot '.env'

if (-not (Test-Path $envFile)) {
    throw 'Missing .env. Copy .env.example to .env and set a private SECRET_KEY first.'
}

Push-Location $repositoryRoot
try {
    Write-Host 'Starting the local MySQL service...'
    & docker compose up -d db
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the database service.' }

    Write-Host 'Building the API image...'
    & docker compose build api
    if ($LASTEXITCODE -ne 0) { throw 'Could not build the API image.' }

    Write-Host 'Applying database migrations...'
    & docker compose run --rm --no-deps api alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }

    Write-Host 'Creating or synchronizing the administrator permission catalog...'
    & docker compose run --rm --no-deps api python -c "import app.main; from app.modules.auth.seed import main; main()"
    if ($LASTEXITCODE -ne 0) { throw 'Administrator seed failed.' }

    Write-Host 'Seeding company defaults...'
    & docker compose run --rm --no-deps api python -m app.modules.company_settings.seed
    if ($LASTEXITCODE -ne 0) { throw 'Company settings seed failed.' }

    Write-Host 'Seeding reusable demo master data...'
    & docker compose run --rm --no-deps api python -c "import app.main; from app.demo_seed import main; main()"
    if ($LASTEXITCODE -ne 0) { throw 'Demo data seed failed.' }

    Write-Host 'Starting the local development application...'
    & docker compose up --build -d
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the application services.' }

    $healthReady = $false
    $lastHealthError = 'No response received.'
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri 'http://localhost:8000/health' -TimeoutSec 3 -UseBasicParsing
            if ($response.StatusCode -eq 200) {
                $healthReady = $true
                break
            }
            $lastHealthError = "Unexpected HTTP status $($response.StatusCode)."
        } catch {
            $lastHealthError = $_.Exception.Message
        }
        Start-Sleep -Seconds 2
    }
    if (-not $healthReady) {
        & docker compose logs --tail 60 api
        throw "API health check failed: $lastHealthError"
    }

    $webReady = $false
    $lastWebError = 'No response received.'
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri 'http://localhost:3000/login' -TimeoutSec 3 -UseBasicParsing
            if ($response.StatusCode -eq 200) {
                $webReady = $true
                break
            }
            $lastWebError = "Unexpected HTTP status $($response.StatusCode)."
        } catch {
            $lastWebError = $_.Exception.Message
        }
        Start-Sleep -Seconds 2
    }
    if (-not $webReady) {
        & docker compose logs --tail 60 web
        throw "Login page health check failed: $lastWebError"
    }

    if (-not $SkipFullCycleTest) {
        Write-Host 'Running the isolated full-cycle API test...'
        & docker compose run --rm api pytest -q tests/test_full_cycle.py
        if ($LASTEXITCODE -ne 0) { throw 'Full-cycle API test failed.' }
    }

    Write-Host ''
    Write-Host 'Demo environment is ready.'
    Write-Host 'Web sign-in: http://localhost:3000/login'
    Write-Host 'API health:  http://localhost:8000/health'
    Write-Host 'OpenAPI UI:  http://localhost:8000/docs'
    Write-Host 'The first admin seed prints a temporary password only when it creates the account.'
    Write-Host 'This is a local development/demo setup, not a production deployment.'
} finally {
    Pop-Location
}
