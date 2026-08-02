param([string]$ApiUrl = "http://127.0.0.1:8000")

$ErrorActionPreference = "Stop"
function ConvertTo-Utf8JsonBytes {
    param([object]$Value, [int]$Depth = 20)
    return ,([System.Text.Encoding]::UTF8.GetBytes(($Value | ConvertTo-Json -Depth $Depth -Compress)))
}
$health = Invoke-RestMethod -Uri "$ApiUrl/health"
if ($health.status -ne "ok") { throw "Health check failed." }

$demo = Invoke-RestMethod -Uri "$ApiUrl/api/v1/demo"
$analysisBody = ConvertTo-Utf8JsonBytes -Value $demo -Depth 100
$analysis = Invoke-RestMethod -Method Post -Uri "$ApiUrl/api/v1/analyze" -ContentType "application/json" -Body $analysisBody
$reloadedWorkflow = Invoke-RestMethod -Uri "$ApiUrl/api/v1/workflow-runs/$($analysis.workflow_run_id)"
if ($reloadedWorkflow.case_id -ne $analysis.case_id) { throw "Workflow persistence failed." }

$baselineBody = ConvertTo-Utf8JsonBytes -Value @{ case = $demo } -Depth 100
$baselines = Invoke-RestMethod -Method Post -Uri "$ApiUrl/api/v1/baselines/run" -ContentType "application/json" -Body $baselineBody
if ($baselines.systems.Count -ne 4) { throw "Baseline comparison failed." }

$configuration = @{ seed = 104; identities = 2; records_per_identity = 2 }
$datasetBody = ConvertTo-Utf8JsonBytes -Value @{ configuration = $configuration }
$dataset = Invoke-RestMethod -Method Post -Uri "$ApiUrl/api/v1/benchmark/generate" -ContentType "application/json" -Body $datasetBody
$benchmarkBody = ConvertTo-Utf8JsonBytes -Value @{ dataset = $dataset; provider_mode = "mock"; candidate_k = 3 } -Depth 100
$benchmark = Invoke-RestMethod -Method Post -Uri "$ApiUrl/api/v1/benchmark/run" -ContentType "application/json" -Body $benchmarkBody
if ($benchmark.systems.Count -ne 4) { throw "Benchmark run failed." }

$ablationBody = ConvertTo-Utf8JsonBytes -Value @{ configuration = $configuration; disabled_nodes = @("rivals"); provider_mode = "mock" }
$ablation = Invoke-RestMethod -Method Post -Uri "$ApiUrl/api/v1/ablation/run" -ContentType "application/json" -Body $ablationBody
if ($ablation.configurations.Count -lt 2) { throw "Ablation run failed." }

$cases = Invoke-RestMethod -Uri "$ApiUrl/api/v1/trials/cases"
if ($cases.Count -ne 8) { throw "Expected eight trial cases." }

$previewBody = ConvertTo-Utf8JsonBytes -Value @{ case_id = "TRIAL-005"; mutation_types = @("prompt_injection"); seed = 104; provider_mode = "mock" }
$preview = Invoke-RestMethod -Method Post -Uri "$ApiUrl/api/v1/trials/preview" -ContentType "application/json" -Body $previewBody
if ($preview.mutations.Count -ne 1) { throw "Trial preview failed." }

$run = Invoke-RestMethod -Method Post -Uri "$ApiUrl/api/v1/trials/run" -ContentType "application/json" -Body $previewBody
$stored = Invoke-RestMethod -Uri "$ApiUrl/api/v1/results/$($run.result_id)"
if ($stored.result_type -ne "trial") { throw "Stored result reload failed." }

$reviewBody = ConvertTo-Utf8JsonBytes -Value @{ case_id = $analysis.case_id; candidate_id = $analysis.candidates[0].candidate_id; outcome = "request_more_information"; reviewer_id = "integration-smoke"; notes = "Request an independent synthetic source." }
$review = Invoke-RestMethod -Method Post -Uri "$ApiUrl/api/v1/reviews" -ContentType "application/json" -Body $reviewBody
$audit = Invoke-RestMethod -Uri "$ApiUrl/api/v1/cases/$($analysis.case_id)/audit"
if ($audit.event_id -notcontains $review.audit_event_id) { throw "Review audit persistence failed." }

$job = Invoke-RestMethod -Method Post -Uri "$ApiUrl/api/v1/jobs/trial" -ContentType "application/json" -Body $previewBody
for ($attempt = 0; $attempt -lt 80; $attempt++) {
    $job = Invoke-RestMethod -Uri "$ApiUrl/api/v1/jobs/$($job.job_id)"
    if ($job.state -in @("completed", "failed", "cancelled")) { break }
    Start-Sleep -Milliseconds 100
}
if ($job.state -ne "completed" -or -not $job.result_id) { throw "Trial job failed: $($job.error)" }

$exportBody = ConvertTo-Utf8JsonBytes -Value @{ format = "json" }
$export = Invoke-RestMethod -Method Post -Uri "$ApiUrl/api/v1/results/$($job.result_id)/export" -ContentType "application/json" -Body $exportBody
if ($export.contains_credentials -ne $false -or -not $export.content_sha256) { throw "Export manifest failed." }
$report = Invoke-RestMethod -Method Post -Uri "$ApiUrl/api/v1/results/$($job.result_id)/report"
if (-not $report.markdown.StartsWith("# THREADLINE")) { throw "Research report failed." }

Write-Host "Integration smoke passed: health, demo/analyze/reload, 4 baselines, benchmark, ablation, 8 trial fixtures, mutation preview/run, review/audit, durable job/result, export, and report."
