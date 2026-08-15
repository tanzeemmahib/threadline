# THREADLINE V1 offline proof launcher

## Start

From the repository root:

```powershell
.\scripts\run-v1-demo.ps1
```

If Windows reports that script execution is disabled, use a process-scoped override (it does
not change the machine policy):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-v1-demo.ps1
```

The script starts the real backend and a production frontend build when those services are not
already running. It uses a temporary SQLite demo database and does not alter source fixtures.

Expected terminal markers:

```text
THREADLINE V1 DEMO READY
passing_run_id=... contract_id=... contract_status=passed_with_review_requirements audit=verified
blocked_run_id=... contract_status=blocked
review_run_id=... classification=insufficient_evidence
replay_id=... status=exact_match
counterfactual_id=... changed=True
passing_workspace=http://127.0.0.1:3000/workspace?run=...
blocked_workspace=http://127.0.0.1:3000/workspace?run=...
```

## Primary judge sequence

Open `http://127.0.0.1:3000/demo?demo=guided` and use the eight-scene evidence challenge documented in `docs/submission/demo-script.md`. It compares the same fictional record packet under a deterministic single-prompt replay and the full workflow, opens exact spans, retains conflicts and a rival, shows the release contract, and ends at authorized human review.

The persisted API paths below are a deeper technical fallback, not the primary four-minute story.

1. Open the passing workspace URL. Show the exact source spans, the 18 rule outcomes, valid audit event count and terminal hash, exact replay status, source-removal certificate, and lineage path.
2. Open the blocked URL. The double-border withheld header, absent classification, critical hard-conflict policy rule, and remediation replace persuasive recommendation content.
3. Use the printed `review_run_id` to open `http://127.0.0.1:3000/workspace?run=<review_run_id>` if desired. The launcher prints the ID, not a separate review URL. The workspace shows `insufficient_evidence`, rivals, and a first-class abstention basis.
4. Point to the tamper-smoke terminal output: `status=broken`, exact invalid event ID, and sequence. The script altered only a copied temporary database.
5. Point to the held-out note: `4 / 4` different-identity cases were withheld, but the conditional 95% Wilson upper bound is `48.989%` because there were only four negative opportunities. The predeclared `10.0%` demonstration target was not met.

## Manual API fallbacks

```powershell
$passing = Invoke-RestMethod http://127.0.0.1:8000/api/v1/demo/v1/passing
$analysis = Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/analyze -ContentType application/json -Body ($passing | ConvertTo-Json -Depth 100)
Invoke-RestMethod http://127.0.0.1:8000/api/v1/runs/$($analysis.workflow_run_id)/audit/verify
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/runs/$($analysis.workflow_run_id)/replay
```

## Expected statuses

- Passing: contract `passed_with_review_requirements`, release `released`, audit `verified`.
- Blocked hard conflict under configured incident policy: contract `blocked`, release `withheld`, classification `null`.
- Review-required abstention: classification `insufficient_evidence`, authorized review routing retained.
- Copied-database tamper: audit `broken`, first invalid event identified.
- Replay: `exact_match` in deterministic mock mode.
- Counterfactual: source removal changes classification or candidate availability and names the first changed workflow node.

If the frontend is unavailable, the API results and `shared/evaluation/threadline-v1.json` are complete fallback artifacts. No screenshot is used as proof of a backend result.
