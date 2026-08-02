param(
    [string]$ApiUrl = "http://127.0.0.1:8000",
    [int]$Port = 3000
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $repositoryRoot "frontend"
$env:NEXT_PUBLIC_API_URL = $ApiUrl
$packageManager = if (Get-Command pnpm -ErrorAction SilentlyContinue) { "pnpm" } else { "npm" }

Write-Host "THREADLINE frontend: http://127.0.0.1:$Port"
Push-Location $frontendRoot
try {
    & $packageManager run dev -- --port $Port
}
finally {
    Pop-Location
}
