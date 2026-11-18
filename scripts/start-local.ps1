<#
Starts ResRef's local development servers in separate PowerShell windows.
The backend uses backend/.env, which intentionally selects the local
backend/db.sqlite3 database when DATABASE_URL is absent.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$backendPath = Join-Path $workspaceRoot 'backend'
$frontendPath = Join-Path $workspaceRoot 'frontend'
$pythonPath = Join-Path $backendPath '.venv\Scripts\python.exe'

if (-not (Test-Path $pythonPath)) {
    throw "Python virtual environment is missing. Run: cd '$backendPath'; py -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}
if (-not (Test-Path (Join-Path $frontendPath 'node_modules'))) {
    throw "Frontend dependencies are missing. Run: cd '$frontendPath'; npm ci"
}

Push-Location $backendPath
try {
    & $pythonPath manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) { throw 'Django migrations failed.' }
}
finally {
    Pop-Location
}

$backendCommand = "Set-Location '$backendPath'; & '$pythonPath' manage.py runserver 127.0.0.1:8000"
$frontendCommand = "Set-Location '$frontendPath'; npm run dev -- --host 127.0.0.1"
Start-Process powershell -ArgumentList '-NoExit', '-Command', $backendCommand | Out-Null
Start-Process powershell -ArgumentList '-NoExit', '-Command', $frontendCommand | Out-Null

Write-Host 'ResRef is starting locally:' -ForegroundColor Green
Write-Host '  Frontend: http://127.0.0.1:5173/'
Write-Host '  API:      http://127.0.0.1:8000/api/health/'
