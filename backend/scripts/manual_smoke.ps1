param(
    [Parameter(Mandatory = $true)]
    [string]$PythonPath,
    [int]$Port = 18765
)

$ErrorActionPreference = 'Stop'
$baseUri = "http://127.0.0.1:$Port"

function Invoke-JsonPost {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Uri,
        [Parameter(Mandatory = $true)]
        [object]$Payload,
        [int]$Depth = 30
    )
    $json = $Payload | ConvertTo-Json -Depth $Depth -Compress
    $body = [System.Text.Encoding]::UTF8.GetBytes($json)
    Invoke-RestMethod -Method Post -Uri $Uri -ContentType 'application/json; charset=utf-8' -Body $body
}

$server = Start-Process -FilePath $PythonPath `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', $Port `
    -WorkingDirectory (Split-Path -Parent $PSScriptRoot) `
    -WindowStyle Hidden `
    -PassThru

try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt += 1) {
        try {
            $health = Invoke-RestMethod -Uri "$baseUri/health" -TimeoutSec 2
            $ready = $true
            break
        }
        catch {
            Start-Sleep -Milliseconds 250
        }
    }
    if (-not $ready) {
        throw 'Server did not become ready.'
    }

    $demo = Invoke-RestMethod -Uri "$baseUri/api/v1/demo"
    $analysisPayload = @{
        incident = $demo.incident
        records = @($demo.records[0], $demo.records[1], $demo.records[2])
        options = @{
            provider_mode = 'mock'
            include_workflow_trace = $true
            candidate_limit = 5
            disabled_nodes = @()
            adjudicator_count = 2
        }
    }
    $analysis = Invoke-JsonPost -Uri "$baseUri/api/v1/analyze" -Payload $analysisPayload
    $baselines = Invoke-JsonPost `
        -Uri "$baseUri/api/v1/baselines/run" `
        -Payload @{ case = $analysisPayload }

    $configuration = @{
        seed = 44
        identities = 3
        records_per_identity = 2
        languages = @('English', 'Arabic', 'French')
        transliteration_severity = 35
        spelling_corruption = 12
        missing_field_percentage = 24
        estimated_age_variance = 2
        changed_location_frequency = 30
        duplicate_record_frequency = 8
        contradictory_timestamp_frequency = 10
        rival_candidate_count = 2
        prompt_injection_frequency = 5
        common_name_frequency = 18
    }
    $generated = Invoke-JsonPost `
        -Uri "$baseUri/api/v1/benchmark/generate" `
        -Payload @{ configuration = $configuration } `
        -Depth 10
    $benchmark = Invoke-JsonPost `
        -Uri "$baseUri/api/v1/benchmark/run" `
        -Payload @{
            configuration = $configuration
            provider_mode = 'mock'
            candidate_k = 5
        } `
        -Depth 10
    $ablation = Invoke-JsonPost `
        -Uri "$baseUri/api/v1/ablation/run" `
        -Payload @{
            configuration = $configuration
            disabled_nodes = @('normalization')
            provider_mode = 'mock'
        } `
        -Depth 10

    [pscustomobject]@{
        health = $health.status
        demo_records = $demo.records.Count
        analyze_status = $analysis.status
        analyze_nodes = $analysis.workflow_trace_details.Count
        baseline_systems = $baselines.systems.Count
        benchmark_id = $generated.benchmark_id
        benchmark_systems = $benchmark.systems.Count
        ablation_configurations = $ablation.configurations.Count
    }
}
finally {
    if ($server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id
    }
}
