<#
Starts the Component 1 API in LIVE mode against the local Ollama model "c1-req" (no replay, no mock).
Run from anywhere:  powershell -ExecutionPolicy Bypass -File scripts\run_c1_live.ps1 [-Port 8000]
Another port is only needed if something else uses 8000; then set VITE_C1_API_BASE=http://127.0.0.1:<port> for the web app (project/apps/web/.env.example).
More browser origins than http://localhost:5173 and http://127.0.0.1:5173: set C1_CORS_ORIGINS (comma separated) before starting.
Stop with Ctrl+C. Changing the backend mode needs a restart of this script.
#>
param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$project = Join-Path $root 'project'
$model = 'c1-req'
$ollama = 'http://localhost:11434'

$env:C1_GENERATION_BACKEND = 'ollama'
$env:LLM_BASE_URL = "$ollama/v1"
$env:LLM_MODEL = $model
$env:LLM_API_KEY = 'ollama'   # dummy value, Ollama ignores it
$env:LLM_TIMEOUT = '600'

try {
    $tags = Invoke-RestMethod -Uri "$ollama/api/tags" -TimeoutSec 5
} catch {
    Write-Host "Ollama is not reachable at $ollama." -ForegroundColor Red
    Write-Host "Fix: start it (open the Ollama app, or run 'ollama serve' in another terminal) and run this script again."
    exit 1
}
$names = @($tags.models | ForEach-Object { $_.name })
if (-not ($names -contains $model -or $names -contains "${model}:latest")) {
    Write-Host "Ollama is running but the model '$model' is not installed. Installed: $($names -join ', ')" -ForegroundColor Red
    Write-Host "Fix: cd project\models\component1\part_b ; ollama create $model -f Modelfile"
    exit 1
}
Write-Host "Ollama OK, model '$model' found. Starting the API in LIVE mode on http://127.0.0.1:$Port ..." -ForegroundColor Green

$py = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }
Set-Location $project   # the package 'agents' lives in project\
& $py -m uvicorn agents.requirement_agent.api.app:app --port $Port
