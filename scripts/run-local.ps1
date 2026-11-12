$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    $pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        throw 'Create .venv and install requirements.txt first. See README.md.'
    }
    $env:PYTHONIOENCODING = 'utf-8'
    $env:DJANGO_DEBUG = 'True'
    & $pythonPath scripts/setup_local.py
    if ($LASTEXITCODE -ne 0) { throw 'Local setup failed.' }
    & $pythonPath manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) { throw 'Migration failed.' }
    & $pythonPath manage.py seed_demo
    if ($LASTEXITCODE -ne 0) { throw 'Demo initialization failed.' }
    Write-Host 'Open http://127.0.0.1:8002/ - choose Staff or Admin; no password needed.'
    & $pythonPath manage.py runserver 127.0.0.1:8002
} finally {
    Pop-Location
}
