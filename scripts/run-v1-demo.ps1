[CmdletBinding()]
param(
    [ValidateNotNullOrEmpty()]
    [string]$BackendUrl = "http://127.0.0.1:8010",

    [ValidateNotNullOrEmpty()]
    [string]$FrontendUrl = "http://127.0.0.1:3000"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$backendBaseUrl = $BackendUrl.TrimEnd("/")
$frontendBaseUrl = $FrontendUrl.TrimEnd("/")
$backendUri = [System.Uri]$backendBaseUrl
$frontendUri = [System.Uri]$frontendBaseUrl

if (-not $backendUri.IsAbsoluteUri -or $backendUri.Scheme -notin @("http", "https")) {
    throw "BackendUrl must be an absolute HTTP(S) URL. Received: $BackendUrl"
}
if (-not $frontendUri.IsAbsoluteUri -or $frontendUri.Scheme -notin @("http", "https")) {
    throw "FrontendUrl must be an absolute HTTP(S) URL. Received: $FrontendUrl"
}

$backendPort = if ($backendUri.IsDefaultPort) {
    if ($backendUri.Scheme -eq "https") { 443 } else { 80 }
} else {
    $backendUri.Port
}
$frontendPort = if ($frontendUri.IsDefaultPort) {
    if ($frontendUri.Scheme -eq "https") { 443 } else { 80 }
} else {
    $frontendUri.Port
}
$loopbackHosts = @("127.0.0.1", "localhost", "::1")
$venvPython = Join-Path $repoRoot "backend\.venv\Scripts\python.exe"
$pythonExecutable = if ($env:THREADLINE_PYTHON -and (Test-Path $env:THREADLINE_PYTHON)) {
    (Get-Item $env:THREADLINE_PYTHON).FullName
} elseif (Test-Path -LiteralPath $venvPython) {
    (Get-Item $venvPython).FullName
} else {
    (Get-Command python -ErrorAction Stop).Source
}
$npmCommand = Get-Command npm.cmd -ErrorAction Stop
$demoDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("threadline-v1-demo-{0}" -f ([guid]::NewGuid().ToString("N")))
$demoDatabase = Join-Path $demoDirectory "threadline-v1-demo.db"
$demoExportDirectory = Join-Path $demoDirectory "exports"
New-Item -ItemType Directory -Force -Path $demoExportDirectory | Out-Null

function Get-EndpointStatus([string]$Url, [int]$TimeoutSeconds = 2) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec $TimeoutSeconds
        return [int]$response.StatusCode
    } catch {
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            return [int]$_.Exception.Response.StatusCode
        }
        return $null
    }
}

function Test-TcpListener([string]$HostName, [int]$Port, [int]$TimeoutMilliseconds = 750) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.ConnectAsync($HostName, $Port)
        if (-not $connect.Wait($TimeoutMilliseconds)) { return $false }
        return $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Wait-Endpoint([string]$Url, [int]$Attempts = 40) {
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        $status = Get-EndpointStatus $Url
        if ($null -ne $status -and $status -ge 200 -and $status -lt 300) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "Endpoint did not become ready: $Url"
}

function Assert-V1Backend([string]$BaseUrl, [bool]$CallerOwned) {
    $proofUrl = "$BaseUrl/api/v1/demo/v1/passing"
    $proofStatus = Get-EndpointStatus $proofUrl
    if ($null -ne $proofStatus -and $proofStatus -ge 200 -and $proofStatus -lt 300) { return }

    $ownership = if ($CallerOwned) { "caller-owned" } else { "newly spawned" }
    throw (
        "The $ownership backend at $BaseUrl does not expose the THREADLINE V1 proof route " +
        "GET /api/v1/demo/v1/passing (HTTP status: $proofStatus). Stop or upgrade that backend, " +
        "or rerun with -BackendUrl pointing to an unused local port. The demo runner will not " +
        "attach to a stale or incompatible service."
    )
}

$healthStatus = Get-EndpointStatus "$backendBaseUrl/health"
$backendPortOccupied = Test-TcpListener $backendUri.Host $backendPort
if ($null -ne $healthStatus -and $healthStatus -ge 200 -and $healthStatus -lt 300) {
    $backendProcess = $null
    Assert-V1Backend $backendBaseUrl $true
} elseif ($backendPortOccupied) {
    throw (
        "A process is already listening at $backendBaseUrl, but its /health endpoint is not " +
        "compatible (HTTP status: $healthStatus). Stop that process or choose an unused local " +
        "port with -BackendUrl. Nothing was started or replaced."
    )
} else {
    if ($backendUri.Scheme -ne "http" -or $backendUri.Host -notin $loopbackHosts) {
        throw (
            "No backend is running at $backendBaseUrl. Automatic startup is restricted to a " +
            "local HTTP BackendUrl (localhost, 127.0.0.1, or ::1)."
        )
    }

    $environmentOverrides = @{
        LLM_PROVIDER = "mock"
        THREADLINE_PROVIDER_MODE = "mock"
        LLM_API_KEY = "threadline-local-mock-placeholder"
        THREADLINE_OPENAI_API_KEY = "threadline-local-mock-placeholder"
        LLM_BASE_URL = "http://127.0.0.1:9/mock-provider-disabled"
        LLM_BASE_URI = "http://127.0.0.1:9/mock-provider-disabled"
        THREADLINE_OPENAI_BASE_URL = "http://127.0.0.1:9/mock-provider-disabled"
        LLM_MODEL = "threadline-local-mock"
        THREADLINE_OPENAI_MODEL = "threadline-local-mock"
        THREADLINE_DATABASE_PATH = $demoDatabase
        THREADLINE_EXPORT_DIRECTORY = $demoExportDirectory
        FRONTEND_ORIGINS = $frontendUri.GetLeftPart([System.UriPartial]::Authority)
    }
    $savedEnvironment = @{}
    foreach ($name in $environmentOverrides.Keys) {
        $existing = Get-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
        $savedEnvironment[$name] = @{
            Exists = $null -ne $existing
            Value = if ($null -ne $existing) { $existing.Value } else { $null }
        }
        Set-Item -LiteralPath "Env:$name" -Value $environmentOverrides[$name]
    }

    try {
        $backendProcess = Start-Process -FilePath $pythonExecutable -ArgumentList "-m", "uvicorn", "app.main:app", "--host", $backendUri.Host, "--port", "$backendPort" -WorkingDirectory (Join-Path $repoRoot "backend") -WindowStyle Hidden -PassThru
    } finally {
        foreach ($name in $environmentOverrides.Keys) {
            if ($savedEnvironment[$name].Exists) {
                Set-Item -LiteralPath "Env:$name" -Value $savedEnvironment[$name].Value
            } else {
                Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
            }
        }
    }

    Wait-Endpoint "$backendBaseUrl/health"
    Assert-V1Backend $backendBaseUrl $false
}

$frontendStatus = Get-EndpointStatus $frontendBaseUrl
if ($null -ne $frontendStatus -and $frontendStatus -ge 200 -and $frontendStatus -lt 500) {
    $frontendProcess = $null
    $callerOwnedFrontend = $true
    Write-Warning (
        "A caller-owned frontend is already running at $frontendBaseUrl. Its backend rewrite " +
        "will be verified against the selected BackendUrl after the demo runs are created. " +
        "If verification fails, rerun with -FrontendUrl pointing to an unused local port."
    )
} else {
    if (Test-TcpListener $frontendUri.Host $frontendPort) {
        throw (
            "A process is already listening at $frontendBaseUrl but did not return a usable " +
            "HTTP response (status: $frontendStatus). Stop it or choose another -FrontendUrl."
        )
    }
    if ($frontendUri.Scheme -ne "http" -or $frontendUri.Host -notin $loopbackHosts) {
        throw (
            "No frontend is running at $frontendBaseUrl. Automatic startup is restricted to a " +
            "local HTTP FrontendUrl (localhost, 127.0.0.1, or ::1)."
        )
    }

    $frontendDirectory = Join-Path $repoRoot "frontend"
    $existingBackendUrlEnvironment = Get-Item -LiteralPath "Env:THREADLINE_BACKEND_URL" -ErrorAction SilentlyContinue
    $savedBackendUrlEnvironment = @{
        Exists = $null -ne $existingBackendUrlEnvironment
        Value = if ($null -ne $existingBackendUrlEnvironment) { $existingBackendUrlEnvironment.Value } else { $null }
    }
    Set-Item -LiteralPath "Env:THREADLINE_BACKEND_URL" -Value $backendBaseUrl
    try {
        Push-Location $frontendDirectory
        try {
            & $npmCommand.Source run build
            if ($LASTEXITCODE -ne 0) { throw "Frontend production build failed." }
        } finally {
            Pop-Location
        }
        $frontendProcess = Start-Process -FilePath $npmCommand.Source -ArgumentList "run", "start", "--", "--hostname", $frontendUri.Host, "--port", "$frontendPort" -WorkingDirectory $frontendDirectory -WindowStyle Hidden -PassThru
    } finally {
        if ($savedBackendUrlEnvironment.Exists) {
            Set-Item -LiteralPath "Env:THREADLINE_BACKEND_URL" -Value $savedBackendUrlEnvironment.Value
        } else {
            Remove-Item -LiteralPath "Env:THREADLINE_BACKEND_URL" -ErrorAction SilentlyContinue
        }
    }
    $callerOwnedFrontend = $false
    Wait-Endpoint $frontendBaseUrl 80
}

function Invoke-DemoAnalysis([string]$Scenario) {
    $request = Invoke-RestMethod -Uri "$backendBaseUrl/api/v1/demo/v1/$Scenario"
    $body = $request | ConvertTo-Json -Depth 100
    return Invoke-RestMethod -Method Post -Uri "$backendBaseUrl/api/v1/analyze" -ContentType "application/json" -Body $body
}

$passing = Invoke-DemoAnalysis "passing"
$blocked = Invoke-DemoAnalysis "blocked"
$review = Invoke-DemoAnalysis "review"
if ($callerOwnedFrontend) {
    $proxiedRunUrl = "$frontendBaseUrl/backend-api/api/v1/runs/$($passing.workflow_run_id)"
    $proxiedRunStatus = Get-EndpointStatus $proxiedRunUrl
    if ($null -eq $proxiedRunStatus -or $proxiedRunStatus -lt 200 -or $proxiedRunStatus -ge 300) {
        throw (
            "The caller-owned frontend at $frontendBaseUrl could not retrieve the run created " +
            "by $backendBaseUrl through its /backend-api rewrite (HTTP status: $proxiedRunStatus). " +
            "Its backend binding cannot be trusted. Rerun with -FrontendUrl pointing to an unused " +
            "local port so this script can build it with THREADLINE_BACKEND_URL=$backendBaseUrl."
        )
    }
}
if ($passing.contract_release_status -ne "released") { throw "Passing scenario was not released." }
if ($passing.evidence_contract.contract_status -ne "passed_with_review_requirements") { throw "Review-required contract state was not exercised." }
if ($blocked.contract_release_status -ne "withheld") { throw "Blocked contradiction scenario was not withheld." }
if ($review.evidence_contract.classification -ne "insufficient_evidence") { throw "Review scenario did not abstain." }

$passingIntegrity = Invoke-RestMethod -Uri "$backendBaseUrl/api/v1/runs/$($passing.workflow_run_id)/audit/verify"
$blockedIntegrity = Invoke-RestMethod -Uri "$backendBaseUrl/api/v1/runs/$($blocked.workflow_run_id)/audit/verify"
if (-not $passingIntegrity.valid -or -not $blockedIntegrity.valid) { throw "An audit chain failed before tamper testing." }

$replay = Invoke-RestMethod -Method Post -Uri "$backendBaseUrl/api/v1/runs/$($passing.workflow_run_id)/replay"
if ($replay.replay_status -ne "exact_match") { throw "Deterministic replay did not match exactly." }
$counterfactualBody = @{
    candidate_id = $passing.candidates[0].candidate_id
    counterfactual_type = "remove_source_record"
    source_record_id = $passing.candidates[0].record_a_id
} | ConvertTo-Json
$counterfactual = Invoke-RestMethod -Method Post -Uri "$backendBaseUrl/api/v1/runs/$($passing.workflow_run_id)/counterfactuals" -ContentType "application/json" -Body $counterfactualBody
if (-not $counterfactual.decision_changed) { throw "Curated counterfactual did not change the decision." }

if (Test-Path $demoDatabase) {
    & $pythonExecutable (Join-Path $repoRoot "backend/scripts/audit_tamper_smoke.py") --database $demoDatabase --run-id $passing.workflow_run_id
    if ($LASTEXITCODE -ne 0) { throw "Copied-database audit tamper smoke failed." }
} else {
    Write-Output "Tamper smoke skipped because the already-running backend owns a different database path."
}

Write-Output "THREADLINE V1 DEMO READY"
Write-Output "passing_run_id=$($passing.workflow_run_id) contract_id=$($passing.evidence_contract.contract_id) contract_status=$($passing.evidence_contract.contract_status) audit=$($passingIntegrity.status)"
Write-Output "blocked_run_id=$($blocked.workflow_run_id) contract_status=$($blocked.evidence_contract.contract_status)"
Write-Output "review_run_id=$($review.workflow_run_id) classification=$($review.evidence_contract.classification)"
Write-Output "replay_id=$($replay.replay_id) status=$($replay.replay_status)"
Write-Output "counterfactual_id=$($counterfactual.certificate_id) changed=$($counterfactual.decision_changed)"
Write-Output "passing_workspace=$frontendBaseUrl/workspace?run=$($passing.workflow_run_id)"
Write-Output "blocked_workspace=$frontendBaseUrl/workspace?run=$($blocked.workflow_run_id)"
Write-Output "review_workspace=$frontendBaseUrl/workspace?run=$($review.workflow_run_id)"
if ($backendProcess) { Write-Output "backend_process_id=$($backendProcess.Id)" }
if ($frontendProcess) { Write-Output "frontend_process_id=$($frontendProcess.Id)" }
