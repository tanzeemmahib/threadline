param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $repositoryRoot "backend"
$venvPython = Join-Path $backendRoot ".venv\Scripts\python.exe"
$pythonCommand = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { (Get-Command python -ErrorAction Stop).Source }
$arguments = @("-m", "uvicorn", "app.main:app", "--host", $HostAddress, "--port", $Port)
if (-not $NoReload) { $arguments += "--reload" }

Write-Host "THREADLINE backend: http://${HostAddress}:$Port"
& $pythonCommand @arguments
