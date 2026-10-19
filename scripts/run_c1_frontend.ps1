<#
Starts the web app that contains the Component 1 page (project\apps\web, Vite dev server, http://localhost:5173) and installs packages only if node_modules is missing.
Open http://localhost:5173/requirement . Start the C1 API first (scripts\run_c1_live.ps1). The C1 API address comes from VITE_C1_API_BASE (default http://127.0.0.1:8000).
Run:  powershell -ExecutionPolicy Bypass -File scripts\run_c1_frontend.ps1
The old standalone UI (frontend\c1) was removed; the C1 page now lives in the web app.
#>
$ErrorActionPreference = 'Stop'
$ui = Join-Path (Split-Path -Parent $PSScriptRoot) 'project\apps\web'
Set-Location $ui
if (-not (Test-Path 'node_modules')) {
    Write-Host 'node_modules is missing: running npm install ...'
    npm install
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
npm run dev
