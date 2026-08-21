[CmdletBinding()]
param(
    [switch]$Bootstrap,
    [switch]$Check,
    [switch]$CheckManifest,
    [switch]$AllowDirty,
    [switch]$SkipGates,
    [switch]$SkipFrontend,
    [switch]$NoPackage
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $repoRoot "backend"
$frontendRoot = Join-Path $repoRoot "frontend"
$venvPython = Join-Path $backendRoot ".venv\Scripts\python.exe"

if ($Bootstrap) {
    if (-not (Test-Path -LiteralPath $venvPython)) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py -3.11 -m venv (Join-Path $backendRoot ".venv")
        } else {
            $bootstrapPython = (Get-Command python -ErrorAction Stop).Source
            & $bootstrapPython -m venv (Join-Path $backendRoot ".venv")
        }
        if ($LASTEXITCODE -ne 0) { throw "Could not create backend virtual environment." }
    }
    & $venvPython -m pip install -r (Join-Path $backendRoot "requirements-dev.txt") -r (Join-Path $repoRoot "docs\requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "Python dependency bootstrap failed." }
    Push-Location $frontendRoot
    try {
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw "Frontend dependency bootstrap failed." }
        & npx.cmd playwright install chromium
        if ($LASTEXITCODE -ne 0) { throw "Playwright Chromium bootstrap failed." }
    } finally {
        Pop-Location
    }
}

$releasePython = if ($env:THREADLINE_RELEASE_PYTHON) {
    $env:THREADLINE_RELEASE_PYTHON
} elseif (Test-Path -LiteralPath $venvPython) {
    $venvPython
} else {
    (Get-Command python -ErrorAction Stop).Source
}

$arguments = @(
    (Join-Path $repoRoot "scripts\reverie_release.py"),
    "--backend-python", $releasePython,
    "--pdf-python", $releasePython
)
if ($Check) { $arguments += "--check" }
if ($CheckManifest) { $arguments += "--check-manifest" }
if ($AllowDirty) { $arguments += "--allow-dirty" }
if ($SkipGates) { $arguments += "--skip-gates" }
if ($SkipFrontend) { $arguments += "--skip-frontend" }
if ($NoPackage) { $arguments += "--no-package" }

& $releasePython @arguments
exit $LASTEXITCODE
