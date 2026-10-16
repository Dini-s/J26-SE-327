<#
Starts the Component 1 UI (Vite dev server, http://127.0.0.1:5173). Installs packages only if node_modules is missing.
Run:  powershell -ExecutionPolicy Bypass -File scripts\run_c1_frontend.ps1
#>
$ErrorActionPreference = 'Stop'
$ui = Join-Path (Split-Path -Parent $PSScriptRoot) 'frontend\c1'
Set-Location $ui
if (-not (Test-Path 'node_modules')) {
    Write-Host 'node_modules is missing: running npm install ...'
    npm install
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
npm run dev
