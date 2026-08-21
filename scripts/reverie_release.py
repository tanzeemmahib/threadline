"""Cross-platform THREADLINE Reverie release verifier and package builder.

This command is offline by default. It does not install dependencies, call a live
model provider, delete workspace files, or deploy anything. Thin PowerShell and
POSIX wrappers expose the supported command-line interface.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SUBMISSION = DOCS / "submission"
PDF_OUTPUT = ROOT / "output" / "pdf"
RELEASE_OUTPUT = ROOT / "output" / "release"
MANIFEST_PATH = SUBMISSION / "reverie-release-manifest.json"

REQUIRED_PATHS = (
    "README.md",
    "LICENSE",
    "docs/reverie-ml-workflow.svg",
    "docs/reverie-ml-workflow.png",
    "docs/reverie-prompt-comparison.md",
    "docs/reverie-evidence-summary.md",
    "docs/reverie-ml-track-documentation.md",
    "docs/reverie-demo-script.md",
    "docs/reverie-judge-qa.md",
    "docs/reverie-submission-checklist.md",
    "docs/reverie-release.md",
    "backend/app/api/routes/reverie.py",
    "backend/app/baselines/reverie_one_shot.py",
    "backend/app/evaluation/reverie_live.py",
    "backend/app/prompts/templates/reverie_one_shot.v1.txt",
    "backend/app/schemas/reverie_evaluation.py",
    "backend/fixtures/reverie_live_evaluation_v1_1.json",
    "backend/scripts/build_reverie_live_spec_v1_1.py",
    "backend/scripts/build_reverie_prompt_lab.py",
    "backend/scripts/run_reverie_live_evaluation.py",
    "backend/tests/test_reverie_live_evaluation.py",
    "backend/tests/test_reverie_prompt_lab.py",
    "frontend/e2e/reverie-golden.spec.ts",
    "frontend/playwright.config.ts",
    "docs/submission/reverie-prompt-lab.json",
    "docs/submission/results.json",
    "docs/submission/results.csv",
    "docs/submission/raw-outputs.json",
    "docs/submission/ablation-counterfactual.json",
    "docs/submission/benchmark-report.md",
    "docs/submission/data-responsibility.md",
    "docs/submission/reproduction.md",
    "docs/submission/build_reverie_pdfs.py",
    "docs/requirements.txt",
    "output/pdf/threadline-reverie-workflow.pdf",
    "output/pdf/threadline-reverie-prompt-comparison.pdf",
    "output/pdf/threadline-reverie-ml-track-documentation.pdf",
    "output/pdf/threadline-reverie-evidence-summary.pdf",
    "scripts/reverie-release.ps1",
    "scripts/reverie-release.sh",
    "scripts/reverie_release.py",
    ".github/workflows/reverie-release.yml",
    "deploy/README.md",
    "deploy/compose.demo.yml",
)

PACKAGE_PATTERNS = (
    "README.md",
    "LICENSE",
    "docs/reverie-*",
    "docs/hackathon-submission.md",
    "docs/submission/README.md",
    "docs/submission/reproduction.md",
    "docs/submission/benchmark-report.md",
    "docs/submission/data-responsibility.md",
    "docs/submission/results.json",
    "docs/submission/results.csv",
    "docs/submission/raw-outputs.json",
    "docs/submission/ablation-counterfactual.json",
    "docs/submission/reverie-prompt-lab.json",
    "docs/submission/reverie-release-manifest.json",
    "docs/submission/reverie-*.json",
    "docs/submission/*certificate*.json",
    "docs/submission/*robustness*.json",
    "docs/product-screenshots/reverie/*.png",
    "output/pdf/*.pdf",
    "scripts/reverie-release.ps1",
    "scripts/reverie-release.sh",
    "scripts/reverie_release.py",
    "backend/app/api/routes/reverie.py",
    "backend/app/baselines/reverie_one_shot.py",
    "backend/app/evaluation/reverie_live.py",
    "backend/app/prompts/templates/reverie_one_shot.v1.txt",
    "backend/app/schemas/reverie_evaluation.py",
    "backend/fixtures/reverie_live_evaluation_v*.json",
    "backend/scripts/build_reverie_live_spec_v1_1.py",
    "backend/scripts/build_reverie_prompt_lab.py",
    "backend/scripts/run_reverie_live_evaluation.py",
    "backend/tests/test_reverie_live_evaluation.py",
    "backend/tests/test_reverie_prompt_lab.py",
    "frontend/e2e/reverie-golden.spec.ts",
    "frontend/playwright.config.ts",
    "frontend/package.json",
    "frontend/package-lock.json",
    ".github/workflows/reverie-release.yml",
    "deploy/README.md",
    "deploy/compose.demo.yml",
)

SECRET_PATTERNS = {
    "aws_access_key": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "google_api_key": re.compile(rb"AIza[0-9A-Za-z_-]{35}"),
    "openai_style_key": re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    "github_token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
}

SOURCE_TEXT_SUFFIXES = {
    ".css",
    ".csv",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".sh",
    ".svg",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
SOURCE_SCAN_ROOTS = (
    ROOT / "README.md",
    ROOT / ".github",
    ROOT / "deploy",
    ROOT / "scripts",
    ROOT / "backend" / "app",
    ROOT / "backend" / "scripts",
    ROOT / "backend" / "fixtures",
    ROOT / "backend" / "tests",
    ROOT / "frontend" / "src",
    ROOT / "frontend" / "tests",
    ROOT / "frontend" / "e2e",
    ROOT / "frontend" / "package.json",
    ROOT / "frontend" / "package-lock.json",
    ROOT / "frontend" / "playwright.config.ts",
    DOCS,
)
SOURCE_SCAN_EXCLUDED_PARTS = {
    ".git",
    ".next",
    ".tmp",
    ".venv",
    "__pycache__",
    "node_modules",
    "output",
    "tmp",
}

BACKEND_RELEASE_PYTHON_PATHS = (
    "app/api/routes/reverie.py",
    "app/baselines/reverie_one_shot.py",
    "app/evaluation/reverie_live.py",
    "app/schemas/reverie_evaluation.py",
    "scripts/build_reverie_live_spec_v1_1.py",
    "scripts/build_reverie_prompt_lab.py",
    "scripts/run_reverie_live_evaluation.py",
    "tests/test_reverie_live_evaluation.py",
    "tests/test_reverie_prompt_lab.py",
)


@dataclass(slots=True)
class Check:
    check_id: str
    status: str
    detail: str
    command: str | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    check_id: str,
) -> Check:
    printable = subprocess.list2cmdline(command)
    print(f"\n[{check_id}] {printable}", flush=True)
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
    summary = summarize_output(completed.stdout)
    return Check(
        check_id=check_id,
        status="passed" if completed.returncode == 0 else "failed",
        detail=summary or f"exit_code={completed.returncode}",
        command=printable,
    )


def summarize_output(output: str) -> str:
    patterns = (
        r"\b\d+ passed(?:, \d+ failed)?(?:, \d+ warnings?)?",
        r"\b\d+ / \d+ gates passed",
        r"All checks passed!",
        r"cases=\d+",
        r"Integration smoke passed:[^\n]+",
    )
    found: list[str] = []
    for pattern in patterns:
        found.extend(match.group(0) for match in re.finditer(pattern, output, flags=re.IGNORECASE))
    if found:
        return "; ".join(dict.fromkeys(found))
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1][:400] if lines else "completed"


def read_json_url(url: str) -> dict[str, object]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=2) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"non-object JSON response from {url}")
    return payload


def api_integration_smoke(backend_python: str) -> Check:
    """Start the real FastAPI app on an ephemeral loopback port in mock mode."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="threadline-reverie-api-") as temp:
        root = Path(temp)
        env = {
            **os.environ,
            "PYTHONPATH": ".",
            "LLM_PROVIDER": "mock",
            "THREADLINE_PROVIDER_MODE": "mock",
            "THREADLINE_DATABASE_PATH": str(root / "threadline-smoke.db"),
            "THREADLINE_EXPORT_DIRECTORY": str(root / "exports"),
        }
        command = [
            backend_python,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ]
        printable = subprocess.list2cmdline(command)
        print(f"\n[api_integration_smoke] {printable}", flush=True)
        process = subprocess.Popen(
            command,
            cwd=ROOT / "backend",
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        try:
            base = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 20
            last_error = "server did not become ready"
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    break
                try:
                    health = read_json_url(f"{base}/health")
                    if health.get("provider_mode") == "mock":
                        break
                    last_error = f"unexpected health payload: {health}"
                except (OSError, TypeError, ValueError, urllib.error.URLError) as exc:
                    last_error = str(exc)
                    time.sleep(0.15)
            else:
                health = {}
            if process.poll() is not None or health.get("provider_mode") != "mock":
                output = process.stdout.read() if process.stdout else ""
                return Check(
                    "api_integration_smoke",
                    "failed",
                    f"{last_error}; process={process.returncode}; {output[-500:]}",
                    printable,
                )
            prompt_lab = read_json_url(f"{base}/api/v1/reverie/prompt-lab")
            if (
                prompt_lab.get("schema_version") != "threadline-reverie-prompt-lab/1.0.0"
                or len(prompt_lab.get("cases", [])) != 3
            ):
                return Check(
                    "api_integration_smoke",
                    "failed",
                    "Prompt Lab endpoint returned an unexpected artifact",
                    printable,
                )
            live_state = "available"
            try:
                live = read_json_url(f"{base}/api/v1/reverie/live-evaluation")
                if not live.get("schema_version"):
                    raise ValueError("live endpoint omitted schema_version")
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    raise
                body = json.loads(exc.read().decode("utf-8"))
                code = body.get("detail", {}).get("error_code")
                if code != "REVERIE_LIVE_EVALUATION_NOT_MEASURED":
                    raise ValueError(f"unexpected live endpoint 404: {body}") from exc
                live_state = "truthfully not measured"
            return Check(
                "api_integration_smoke",
                "passed",
                f"loopback mock API / health + 3-case Prompt Lab / live evaluation {live_state}",
                printable,
            )
        except (
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            urllib.error.URLError,
        ) as exc:
            return Check("api_integration_smoke", "failed", str(exc), printable)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def repository_state() -> dict[str, object]:
    commit = git("rev-parse", "HEAD")
    status = git("status", "--porcelain=v1", "--untracked-files=all")
    timestamp = git("show", "-s", "--format=%cI", "HEAD")
    return {
        "commit": commit,
        "commit_timestamp": timestamp,
        "branch": git("branch", "--show-current") or "DETACHED",
        "working_tree_clean": not bool(status),
        "change_count": len(status.splitlines()) if status else 0,
    }


def validate_required_files() -> Check:
    missing = [path for path in REQUIRED_PATHS if not (ROOT / path).is_file()]
    if missing:
        return Check("required_files", "failed", "missing: " + ", ".join(missing))
    return Check("required_files", "passed", f"{len(REQUIRED_PATHS)} required files present")


def validate_prompt_lab() -> Check:
    path = SUBMISSION / "reverie-prompt-lab.json"
    artifact = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if artifact.get("schema_version") != "threadline-reverie-prompt-lab/1.0.0":
        errors.append("schema_version")
    if artifact.get("artifact_id") != "THREADLINE-REVERIE-PROMPT-LAB-V1":
        errors.append("artifact_id")
    if artifact.get("synthetic_only") is not True:
        errors.append("synthetic_only")
    if len(artifact.get("cases", [])) != 3:
        errors.append("case_count")
    for relative, expected in artifact.get("source_artifacts", {}).items():
        source = ROOT / relative
        if not source.is_file() or sha256_file(source) != expected:
            errors.append(f"source:{relative}")
    span_count = 0
    for container in [artifact.get("winning_story", {}), *artifact.get("cases", [])]:
        records = {record["record_id"]: record["text"] for record in container.get("records", [])}
        for span in container.get("source_spans", []):
            span_count += 1
            text = records.get(span.get("record_id"), "")
            if text[span.get("start", -1) : span.get("end", -1)] != span.get("quote"):
                errors.append(f"span:{span.get('span_id')}")
    if errors:
        return Check("prompt_lab_artifact", "failed", ", ".join(errors))
    return Check(
        "prompt_lab_artifact",
        "passed",
        f"schema/id/synthetic guard, 3 cases, {len(artifact['source_artifacts'])} source hashes, {span_count} exact spans",
    )


def live_evaluation_publication() -> tuple[dict[str, object], list[str]]:
    spec_path = ROOT / "backend" / "fixtures" / "reverie_live_evaluation_v1_1.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if spec.get("schema_version") != "threadline-reverie-live-evaluation-spec/1.1.0":
        errors.append("spec_schema")
    if spec.get("synthetic_only") is not True:
        errors.append("spec_synthetic_only")
    if len(spec.get("cases", [])) != 3:
        errors.append("spec_case_count")
    source_count = 0
    for entry in [*spec.get("source_files", []), *spec.get("prompts", [])]:
        relative = entry.get("path")
        expected = entry.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            errors.append("malformed_source_entry")
            continue
        source_count += 1
        source = ROOT / relative
        if not source.is_file() or sha256_file(source) != expected:
            errors.append(f"source:{relative}")

    spec_hash = sha256_file(spec_path)
    recorder_dir = ROOT / "backend" / "data" / "reverie_live_evaluation_v1_1"
    work_state_path = recorder_dir / "run-state.json"
    recorder_path = recorder_dir / "raw-provider-calls.json"
    results_path = recorder_dir / "results.json"
    submission_results_path = SUBMISSION / "reverie-live-evaluation-results.json"
    publication_manifest_path = SUBMISSION / "reverie-live-evaluation-manifest.json"
    publication: dict[str, object] = {
        "status": "not_published",
        "spec_path": spec_path.relative_to(ROOT).as_posix(),
        "spec_sha256": spec_hash,
        "pinned_sources": source_count,
        "cases": len(spec.get("cases", [])),
        "repetitions": spec.get("schedule", {}).get("repetitions"),
        "systems": len(spec.get("systems", [])),
        "published_files": [],
    }
    if not results_path.is_file():
        if work_state_path.is_file() or recorder_path.is_file():
            errors.append("partial live recorder exists without a complete results artifact")
            publication["status"] = "partial_blocked"
        if submission_results_path.is_file() or publication_manifest_path.is_file():
            errors.append("submission publication exists without authoritative results")
        return publication, errors

    results = json.loads(results_path.read_text(encoding="utf-8"))
    expected_runs = (
        len(spec.get("cases", []))
        * int(spec.get("schedule", {}).get("repetitions", 0))
        * len(spec.get("systems", []))
    )
    if results.get("schema_version") != "threadline-reverie-live-evaluation-results/1.0.0":
        errors.append("results.json:schema")
    if results.get("status") != "complete":
        errors.append(f"results.json:status={results.get('status')}")
    if results.get("synthetic_only") is not True:
        errors.append("results.json:synthetic_only")
    if results.get("spec_sha256") != spec_hash:
        errors.append("results.json:spec_sha256")
    if results.get("same_input_and_config_verified") is not True:
        errors.append("results.json:same_input_and_config_verified")
    if results.get("expected_system_runs") != expected_runs:
        errors.append("results.json:expected_system_runs")
    if results.get("completed_system_runs") != expected_runs:
        errors.append("results.json:completed_system_runs")
    if results.get("failed_system_runs") != 0:
        errors.append("results.json:failed_system_runs")
    if not results.get("completed_at"):
        errors.append("results.json:completed_at")
    if len(results.get("cases", [])) != len(spec.get("cases", [])) * int(
        spec.get("schedule", {}).get("repetitions", 0)
    ):
        errors.append("results.json:case_repetition_count")
    if not recorder_path.is_file():
        errors.append("raw-provider-calls.json:missing")
    else:
        recorder = json.loads(recorder_path.read_text(encoding="utf-8"))
        if recorder.get("schema_version") != "threadline-live-provider-recorder/1.0.0":
            errors.append("raw-provider-calls.json:schema")
        if recorder.get("spec_sha256") != spec_hash:
            errors.append("raw-provider-calls.json:spec_sha256")
        if recorder.get("contains_credentials") is not False:
            errors.append("raw-provider-calls.json:contains_credentials")
        if results.get("recorder_artifact_sha256") != sha256_file(recorder_path):
            errors.append("results.json:recorder_artifact_sha256")

    if not submission_results_path.is_file():
        errors.append("submission results:missing")
    elif submission_results_path.read_bytes() != results_path.read_bytes():
        errors.append("submission results:not byte-identical")
    if not publication_manifest_path.is_file():
        errors.append("publication manifest:missing")
    else:
        public = json.loads(publication_manifest_path.read_text(encoding="utf-8"))
        public_spec = public.get("spec", {})
        public_results = public.get("results", {})
        public_recorder = public.get("raw_provider_recorder", {})
        public_validation = public.get("validation", {})
        if public.get("schema_version") != "threadline-reverie-live-evaluation-publication/1.0.0":
            errors.append("publication manifest:schema")
        if public_spec.get("sha256") != spec_hash:
            errors.append("publication manifest:spec sha256")
        if public_results.get("sha256") != sha256_file(results_path):
            errors.append("publication manifest:results sha256")
        if public_results.get("byte_identical") is not True:
            errors.append("publication manifest:byte_identical")
        if recorder_path.is_file():
            recorder = json.loads(recorder_path.read_text(encoding="utf-8"))
            if public_recorder.get("sha256") != sha256_file(recorder_path):
                errors.append("publication manifest:recorder sha256")
            if public_recorder.get("contains_credentials") is not False:
                errors.append("publication manifest:recorder credentials")
            if public_recorder.get("logical_call_count") != len(recorder.get("calls", {})):
                errors.append("publication manifest:logical call count")
            if public_recorder.get("transport_attempt_count") != len(
                recorder.get("transport_attempts", [])
            ):
                errors.append("publication manifest:transport attempt count")
        for field, expected in (
            ("strict_result_schema", "LiveEvaluationArtifact"),
            ("strict_recorder_schema", "ProviderRecorderCheckpoint"),
        ):
            if public_validation.get(field) != expected:
                errors.append(f"publication manifest:{field}")
        if public_validation.get("expected_system_runs") != expected_runs:
            errors.append("publication manifest:expected system runs")
        if public_validation.get("complete_system_runs") != expected_runs:
            errors.append("publication manifest:complete system runs")
        if public_validation.get("failed_system_runs") != 0:
            errors.append("publication manifest:failed system runs")

    if not errors:
        publication.update(
            {
                "status": "complete",
                "results_sha256": sha256_file(results_path),
                "recorder_sha256": sha256_file(recorder_path),
                "expected_system_runs": expected_runs,
                "published_files": [
                    results_path.relative_to(ROOT).as_posix(),
                    recorder_path.relative_to(ROOT).as_posix(),
                    submission_results_path.relative_to(ROOT).as_posix(),
                    publication_manifest_path.relative_to(ROOT).as_posix(),
                ],
                "publication_manifest_sha256": sha256_file(publication_manifest_path),
            }
        )
    else:
        publication["status"] = "invalid_or_partial_blocked"
    return publication, errors


def published_live_evidence_files() -> list[Path]:
    publication, errors = live_evaluation_publication()
    if errors or publication.get("status") != "complete":
        return []
    return [ROOT / str(path) for path in publication["published_files"]]


def validate_live_evaluation_artifacts() -> Check:
    publication, errors = live_evaluation_publication()
    if errors:
        return Check("live_evaluation_artifacts", "failed", "; ".join(errors))
    if publication.get("status") != "complete":
        return Check(
            "live_evaluation_artifacts",
            "passed",
            "no live comparison published; manifest records an explicit submission blocker",
        )
    return Check(
        "live_evaluation_artifacts",
        "passed",
        f"complete 3-case x 3-repetition x 2-system comparison / spec={publication['spec_sha256']} / results={publication['results_sha256']}",
    )


def validate_diagram() -> Check:
    svg = DOCS / "reverie-ml-workflow.svg"
    png = DOCS / "reverie-ml-workflow.png"
    ET.parse(svg)
    with png.open("rb") as stream:
        signature = stream.read(24)
    if signature[:8] != b"\x89PNG\r\n\x1a\n":
        return Check("workflow_derivatives", "failed", "invalid PNG signature")
    width, height = struct.unpack(">II", signature[16:24])
    checklist = (DOCS / "reverie-submission-checklist.md").read_text(encoding="utf-8")
    expected = re.search(r"SVG `([0-9a-f]{64})`; PNG `([0-9a-f]{64})`", checklist)
    if not expected:
        return Check("workflow_derivatives", "failed", "recorded workflow hashes missing")
    observed = (sha256_file(svg), sha256_file(png))
    if observed != expected.groups():
        return Check("workflow_derivatives", "failed", "workflow hash drift")
    if (width, height) != (2000, 1200):
        return Check(
            "workflow_derivatives",
            "failed",
            f"unexpected PNG dimensions {width}x{height}",
        )
    return Check(
        "workflow_derivatives",
        "passed",
        f"SVG valid; PNG {width}x{height}; hashes match checklist",
    )


def markdown_files() -> list[Path]:
    return [ROOT / "README.md", *sorted(DOCS.rglob("*.md"))]


def link_target(raw: str) -> str:
    target = raw.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    return target.split(maxsplit=1)[0]


def validate_links() -> Check:
    pattern = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
    checked = 0
    missing: list[str] = []
    for source in markdown_files():
        text = source.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            target = link_target(match.group(1))
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            relative = urllib.parse.unquote(target.split("#", 1)[0])
            if not relative:
                continue
            checked += 1
            if not (source.parent / relative).resolve().exists():
                missing.append(f"{source.relative_to(ROOT)} -> {target}")
    if missing:
        return Check("local_links", "failed", "; ".join(missing[:20]))
    return Check(
        "local_links",
        "passed",
        f"{len(markdown_files())} Markdown files; {checked} local links; 0 missing",
    )


def package_files(include_manifest: bool = True) -> list[Path]:
    paths: set[Path] = set()
    for pattern in PACKAGE_PATTERNS:
        for path in ROOT.glob(pattern):
            if path.is_file() and (include_manifest or path != MANIFEST_PATH):
                paths.add(path.resolve())
    paths.update(path.resolve() for path in published_live_evidence_files())
    return sorted(paths, key=lambda path: path.relative_to(ROOT).as_posix())


def curated_source_files() -> list[Path]:
    """Return production/source text without traversing caches or runtime data.

    The release ZIP remains intentionally narrow. The credential scan is wider:
    it covers application, release, fixture, test, CI, deployment, and submission
    sources so a secret outside the judge packet cannot be overlooked.
    """

    paths: set[Path] = set()
    for root in SOURCE_SCAN_ROOTS:
        candidates = [root] if root.is_file() else root.rglob("*") if root.is_dir() else []
        for path in candidates:
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            if SOURCE_SCAN_EXCLUDED_PARTS.intersection(relative.parts):
                continue
            if path.suffix.lower() in SOURCE_TEXT_SUFFIXES:
                paths.add(path.resolve())
    return sorted(paths, key=lambda path: path.relative_to(ROOT).as_posix())


def validate_secrets(paths: Iterable[Path]) -> Check:
    findings: list[str] = []
    scanned = 0
    for path in paths:
        if path.suffix.lower() in {".png", ".pdf", ".zip"}:
            continue
        payload = path.read_bytes()
        scanned += 1
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(payload):
                findings.append(f"{path.relative_to(ROOT)}:{name}")
    if findings:
        return Check("secret_scan", "failed", ", ".join(findings))
    return Check(
        "secret_scan",
        "passed",
        f"{scanned} curated source files; 0 high-confidence credential patterns",
    )


def pdf_python_ready(executable: str) -> bool:
    completed = subprocess.run(
        [executable, "-c", "import reportlab,pypdf,PIL"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def regenerate_artifacts(*, backend_python: str, pdf_python: str, check_drift: bool) -> list[Check]:
    checks: list[Check] = []
    prompt_path = SUBMISSION / "reverie-prompt-lab.json"
    prompt_before = sha256_file(prompt_path) if prompt_path.exists() else None
    prompt_result = run(
        [backend_python, "scripts/build_reverie_prompt_lab.py"],
        cwd=ROOT / "backend",
        env={**os.environ, "PYTHONPATH": "."},
        check_id="regenerate_prompt_lab",
    )
    if prompt_result.status == "passed":
        prompt_after = sha256_file(prompt_path)
        if check_drift and prompt_before != prompt_after:
            prompt_result.status = "failed"
            prompt_result.detail = f"artifact drift: {prompt_before} -> {prompt_after}"
    checks.append(prompt_result)

    summary_path = DOCS / "reverie-evidence-summary.md"
    summary_before = summary_path.read_text(encoding="utf-8") if summary_path.exists() else None
    summary_payload = evidence_summary_markdown(
        json.loads(prompt_path.read_text(encoding="utf-8")),
        prompt_sha256=sha256_file(prompt_path),
    )
    if check_drift and summary_before != summary_payload:
        checks.append(Check("evidence_summary_markdown", "failed", "Markdown derivative drift"))
    else:
        summary_path.write_text(summary_payload, encoding="utf-8", newline="\n")
        checks.append(
            Check(
                "evidence_summary_markdown",
                "passed",
                "source-backed one-page summary current",
            )
        )

    pdf_paths = sorted(PDF_OUTPUT.glob("threadline-reverie-*.pdf"))
    pdf_before = {path.name: sha256_file(path) for path in pdf_paths}
    if not pdf_python_ready(pdf_python):
        checks.append(
            Check(
                "build_pdfs",
                "failed",
                f"{pdf_python} lacks docs dependencies; run wrapper with --bootstrap/-Bootstrap",
            )
        )
        return checks
    pdf_result = run(
        [pdf_python, "docs/submission/build_reverie_pdfs.py"],
        check_id="build_pdfs",
    )
    if pdf_result.status == "passed" and check_drift:
        pdf_after = {
            path.name: sha256_file(path)
            for path in sorted(PDF_OUTPUT.glob("threadline-reverie-*.pdf"))
        }
        if pdf_before != pdf_after:
            pdf_result.status = "failed"
            pdf_result.detail = "PDF derivative drift"
    checks.append(pdf_result)
    return checks


def live_comparison_summary_section() -> str:
    """Source the measured live same-model comparison from the published artifacts.

    Returns the section body (without surrounding blank lines) or an empty string
    when no complete, published comparison exists.
    """
    results_path = SUBMISSION / "reverie-live-evaluation-results.json"
    if not results_path.is_file():
        return ""
    results = json.loads(results_path.read_text(encoding="utf-8"))
    systems = results.get("aggregate", {}).get("systems", {})
    threadline = systems.get("full_threadline")
    one_shot = systems.get("structured_one_shot")
    if results.get("status") != "complete" or not threadline or not one_shot:
        return ""
    spec_hash = results.get("spec_sha256", "")
    lines = [
        "## Measured live same-model comparison",
        "",
        f"A frozen preregistered comparison (spec `{results.get('spec_id')}`, SHA-256 `{spec_hash}`) ran before any provider output was observed: 3 synthetic cases × 3 repetitions × 2 systems = 18 top-level runs; both systems receive identical records, incident context, provider (`openai_compatible`), model (`Qwen/Qwen3-30B-A3B-Instruct-2507`), and temperature `0`. All 18 runs completed with 0 final failures; every request, response, retry, and error is recorded in a sanitized checkpoint under `backend/data/reverie_live_evaluation_v1_1/`.",
        "",
        "| System (9 runs each) | Schema-valid | Outcome-acceptable | Supported fields | Unsupported fields | Invalid citations | Exact-citation validity |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| THREADLINE workflow | {threadline['schema_valid_runs']} / {threadline['completed_runs']} | {threadline['outcomes_within_accepted_set']} / {threadline['completed_runs']} | {threadline['supported_fields']} | {threadline['unsupported_fields']} | {threadline['invalid_citations']} | n/a (0 exact citations claimed) |",
        f"| Structured one-shot | {one_shot['schema_valid_runs']} / {one_shot['completed_runs']} | {one_shot['outcomes_within_accepted_set']} / {one_shot['completed_runs']} | {one_shot['supported_fields']} | {one_shot['unsupported_fields']} | {one_shot['invalid_citations']} | n/a |",
        "",
        f"The one-shot returned an acceptable classification in all 9 runs, but {one_shot['invalid_citations']} of its {one_shot['supported_fields'] + one_shot['unsupported_fields']} emitted claim spans were inexact (7 invalid citations in every cross-script run). THREADLINE never emitted an unsupported or inexact field across all 9 runs, but abstained (`insufficient_evidence`) in 6 of 9 runs and under-detected the blocking DOB conflict that the deterministic harness blocks. Results are mixed; no superiority claim is made from three synthetic cases. This is measured live-provider evidence, distinct from the deterministic mock replay and the archived Prompt V2/V3 extraction runs.",
        "",
        "- Live-evaluation results SHA-256: `" + sha256_file(results_path) + "`",
    ]
    return "\n".join(lines)


def evidence_summary_markdown(artifact: dict, *, prompt_sha256: str) -> str:
    cohorts = {item["cohort_id"]: item for item in artifact["prompt_iterations"]["cohorts"]}

    def run_for(cohort_id: str, version: str) -> dict:
        return next(run for run in cohorts[cohort_id]["runs"] if run["prompt_version"] == version)

    def metric_row(label: str, run: dict) -> str:
        quality = run["extraction_quality"]
        return (
            f"| {label} | {quality['records_ok']}/{quality['records_total']} | "
            f"{quality['total_tp']} / {quality['total_fp']} / {quality['total_fn']} | "
            f"{quality['micro_precision']:.4f} | {quality['micro_recall']:.4f} | "
            f"{quality['micro_f1']:.4f} |"
        )

    v1 = run_for("targeted-19-record-live-cohort", "v1")
    v2_targeted = run_for("targeted-19-record-live-cohort", "v2")
    v2 = run_for("full-58-record-live-cohort", "v2")
    v3 = run_for("full-58-record-live-cohort", "v3")
    decision = artifact["prompt_iterations"]["promotion_decision"]
    decision_metrics = v2["decision_metrics"]
    story = artifact["winning_story"]
    lines = [
        "# THREADLINE — Reverie evidence summary",
        "",
        "> **One connection recovered. One false merge prevented. Every decision traceable.** “Connection recovered” means a candidate record connection reconstructed for authorized review — not a person identified.",
        "",
        "THREADLINE is a synthetic research demonstration of a source-cited prompt workflow surrounded by deterministic comparison and release policy. It has not been validated for operational humanitarian use.",
        "",
        "## The evidence case",
        "",
        "| Candidate records | Evidence state | Release boundary |",
        "| --- | --- | --- |",
        "| `FAMILY-018 ↔ SHELTER-204` | Supported possible connection | Eligible only for authorized human review; never identity confirmation |",
        "| `FAMILY-018 ↔ HOSPITAL-052` | Document-backed age/timeline contradiction | **BLOCKED** by deterministic material-conflict rules; the model cannot override |",
        "",
        "All three systems in the guided comparison receive the same complete three-record packet. Exact quotes and offsets remain available from the original synthetic source text.",
        "",
        "## Prompt promotion evidence",
        "",
        "| Shared cohort | Schema-valid | TP / FP / FN | Precision | Recall | F1 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        metric_row("Targeted 19 · Prompt V1", v1),
        metric_row("Targeted 19 · Prompt V2", v2_targeted),
        metric_row("Full 58 · Prompt V2 · **PRODUCTION**", v2),
        metric_row("Full 58 · Prompt V3 · **NOT PROMOTED**", v3),
        "",
        f"Prompt V3 was not promoted (`{decision['reason_code']}`): recall increased from `{decision['v2_recall']:.4f}` to `{decision['v3_recall']:.4f}`, but precision fell from `{decision['v2_precision']:.4f}` to `{decision['v3_precision']:.4f}` and false-positive fields rose from `{decision['v2_false_positive_fields']}` to `{decision['v3_false_positive_fields']}` on the same 58 records. No full 58-record V1 artifact exists, so no three-way same-cohort ranking is claimed.",
        "",
        "## Measured safety boundary",
        "",
        f"- Archived full Prompt V2: `{decision_metrics['true_link_count']}` link-recommended candidate pairs; `{decision_metrics['false_merge_count']}/{decision_metrics['different_identity_pairs']}` observed false merges; `{decision_metrics['false_non_match_count']}` false non-links across `{decision_metrics['same_identity_pairs']}` same-identity opportunities.",
        f"- Blocking-conflict recall: `{decision_metrics['blocked_conflict_recall']:.3f}`.",
        f"- Approximate API cost: **{v2['operational']['approximate_api_cost']}**.",
        "- These are small synthetic denominators, not a real-world safety, fairness, or effectiveness claim.",
    ]
    live_section = live_comparison_summary_section()
    if live_section:
        lines.append("")
        lines.append(live_section)
    lines.extend(
        [
            "",
            "## Audit path",
            "",
            "- Guided case: `/demo?demo=guided`",
            "- Prompt Lab: `/prompt-lab`",
            "- Offline release command: `.\\scripts\\reverie-release.ps1` or `bash scripts/reverie-release.sh`",
            f"- Prompt Lab SHA-256: `{prompt_sha256}`",
            f"- Case: `{story['case_id']}`; fictional synthetic records only",
            "",
        ]
    )
    return "\n".join(lines)


def focused_gates(backend_python: str, *, frontend: bool) -> list[Check]:
    checks: list[Check] = []
    with tempfile.TemporaryDirectory(prefix="threadline-reverie-pytest-") as temp:
        base = Path(temp)
        env = {**os.environ, "PYTHONPATH": "."}
        for check_id, target in (
            ("pytest_reverie", "tests/test_reverie_prompt_lab.py"),
            ("pytest_reverie_live", "tests/test_reverie_live_evaluation.py"),
            ("pytest_submission", "tests/test_submission_evidence.py"),
            ("pytest_extraction_contract", "tests/test_phase11_extraction_contract.py"),
        ):
            checks.append(
                run(
                    [
                        backend_python,
                        "-m",
                        "pytest",
                        target,
                        "-q",
                        f"--basetemp={base / check_id}",
                    ],
                    cwd=ROOT / "backend",
                    env=env,
                    check_id=check_id,
                )
            )
        checks.append(
            run(
                [backend_python, "_phase10s_validate.py"],
                cwd=ROOT / "backend",
                env=env,
                check_id="deterministic_validator",
            )
        )
        checks.append(
            run(
                [
                    backend_python,
                    "-m",
                    "ruff",
                    "check",
                    *BACKEND_RELEASE_PYTHON_PATHS,
                ],
                cwd=ROOT / "backend",
                env=env,
                check_id="ruff_submission_scope",
            )
        )
        checks.append(
            run(
                [
                    backend_python,
                    "-m",
                    "ruff",
                    "format",
                    "--check",
                    *BACKEND_RELEASE_PYTHON_PATHS,
                ],
                cwd=ROOT / "backend",
                env=env,
                check_id="ruff_format_submission_scope",
            )
        )
        checks.append(
            run(
                [
                    backend_python,
                    "-m",
                    "mypy",
                    # silent keeps imported module types resolvable while suppressing
                    # pre-existing errors inside imported legacy modules.
                    "--follow-imports=silent",
                    *(
                        path
                        for path in BACKEND_RELEASE_PYTHON_PATHS
                        if not path.startswith("tests/")
                    ),
                ],
                cwd=ROOT / "backend",
                env=env,
                check_id="mypy_submission_scope",
            )
        )
        checks.append(
            run(
                [
                    backend_python,
                    "-m",
                    "ruff",
                    "check",
                    "../scripts/reverie_release.py",
                    "../docs/submission/build_reverie_pdfs.py",
                ],
                cwd=ROOT / "backend",
                env=env,
                check_id="ruff_release_tools",
            )
        )
        checks.append(
            run(
                [
                    backend_python,
                    "-m",
                    "ruff",
                    "format",
                    "--check",
                    "../scripts/reverie_release.py",
                    "../docs/submission/build_reverie_pdfs.py",
                ],
                cwd=ROOT / "backend",
                env=env,
                check_id="ruff_format_release_tools",
            )
        )
        checks.append(api_integration_smoke(backend_python))
    if frontend:
        npm = "npm.cmd" if os.name == "nt" else "npm"
        for check_id, arguments in (
            ("frontend_tests", ["test"]),
            ("frontend_typecheck", ["run", "typecheck"]),
            ("frontend_lint", ["run", "lint"]),
            ("frontend_build", ["run", "build"]),
            ("frontend_golden_e2e", ["run", "test:e2e"]),
        ):
            checks.append(run([npm, *arguments], cwd=ROOT / "frontend", check_id=check_id))
    return checks


def artifact_entry(path: Path) -> dict[str, object]:
    relative = path.relative_to(ROOT).as_posix()
    mime = mimetypes.guess_type(relative)[0] or "application/octet-stream"
    return {
        "path": relative,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "media_type": mime,
        "role": artifact_role(relative),
    }


def artifact_role(path: str) -> str:
    if path.endswith("reverie-live-evaluation-manifest.json"):
        return "live_evaluation_publication_manifest"
    if path.endswith("reverie-live-evaluation-results.json") or path.endswith(
        "reverie_live_evaluation_v1_1/results.json"
    ):
        return "authoritative_live_same_model_comparison"
    if path.endswith("reverie_live_evaluation_v1_1/raw-provider-calls.json"):
        return "sanitized_live_provider_recorder"
    if path.endswith("reverie_live_evaluation_v1_1.json"):
        return "frozen_live_evaluation_spec"
    if "robustness" in path:
        return "robustness_evidence"
    if "certificate" in path:
        return "counterfactual_certificate"
    if path.endswith("reverie-prompt-lab.json"):
        return "authoritative_machine_evidence"
    if path.endswith(("results.json", "results.csv")):
        return "authoritative_benchmark_summary"
    if path.endswith("raw-outputs.json"):
        return "authoritative_raw_outputs"
    if path.endswith(".pdf"):
        return "print_derivative"
    if "/product-screenshots/" in path:
        return "rendered_product_capture"
    if path.endswith(".svg"):
        return "editable_vector"
    if path.endswith(".png"):
        return "raster_derivative"
    if path.endswith(".md") or path == "README.md":
        return "human_readable_documentation"
    return "release_support"


def build_manifest(state: dict[str, object], checks: list[Check]) -> dict[str, object]:
    files = [artifact_entry(path) for path in package_files(include_manifest=False)]
    live_publication, _ = live_evaluation_publication()
    manual_gates = {
        "pdf_visual_review": "required_after_each_generated_revision",
        "keyboard_focus_screen_reader_review": "not_automated_by_release_command",
        "public_deployment": "not_performed_or_claimed",
    }
    known_limits = [
        "Synthetic fixtures only; no operational humanitarian validation.",
        "Archived Prompt V1/V2/V3 live-provider results are single runs, not repeatability evidence.",
        "Zero observed false merges uses a denominator of 8 different-identity opportunities in the archived Prompt V2 run.",
        "The public full-stack application is not deployment-ready: authentication and production governance are absent.",
    ]
    if live_publication.get("status") == "complete":
        known_limits.append(
            "The published same-model comparison contains 3 synthetic cases x 3 repetitions; it remains a small synthetic experiment, not operational validation."
        )
    else:
        known_limits.append(
            "SUBMISSION BLOCKER: no complete published live same-model one-shot versus workflow artifact is available. Partial recorder state is never packaged."
        )
    manifest = {
        "schema_version": "threadline-reverie-release/1.0.0",
        "release_id": "THREADLINE-REVERIE-2026",
        "synthetic_only": True,
        "decision_boundary": "possible record connections for authorized human review only",
        "repository": {
            "commit": state["commit"],
            "commit_timestamp": state["commit_timestamp"],
            "working_tree_clean": state["working_tree_clean"],
            "change_count": state["change_count"],
        },
        "toolchain": {
            "python": ">=3.11",
            "node": "20.x in CI",
            "dependency_locks": [
                "backend/requirements.txt",
                "backend/requirements-dev.txt",
                "docs/requirements.txt",
                "frontend/package-lock.json",
            ],
        },
        "checks": [{"check_id": check.check_id, "status": check.status} for check in checks],
        "live_same_model_comparison": live_publication,
        "manual_gates": manual_gates,
        "routes": ["/", "/demo?demo=guided", "/prompt-lab", "/demo?workspace=1"],
        "known_limits": known_limits,
        "files": files,
    }
    manifest["content_digest_sha256"] = canonical_sha256(files)
    manifest["check_digest_sha256"] = canonical_sha256(manifest["checks"])
    return manifest


def manifest_errors(manifest: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != "threadline-reverie-release/1.0.0":
        errors.append("schema_version")
    if manifest.get("release_id") != "THREADLINE-REVERIE-2026":
        errors.append("release_id")
    if manifest.get("synthetic_only") is not True:
        errors.append("synthetic_only")
    files = manifest.get("files")
    checks = manifest.get("checks")
    if not isinstance(files, list):
        errors.append("files")
        files = []
    if not isinstance(checks, list):
        errors.append("checks")
        checks = []
    paths = [entry.get("path") for entry in files if isinstance(entry, dict)]
    if len(paths) != len(files) or paths != sorted(paths) or len(paths) != len(set(paths)):
        errors.append("file_order_or_uniqueness")
    for entry in files:
        if not isinstance(entry, dict):
            continue
        relative = entry.get("path")
        expected_hash = entry.get("sha256")
        expected_bytes = entry.get("bytes")
        if not isinstance(relative, str) or not re.fullmatch(r"[0-9a-f]{64}", str(expected_hash)):
            errors.append(f"file_entry:{relative}")
            continue
        path = ROOT / relative
        if (
            not path.is_file()
            or path.stat().st_size != expected_bytes
            or sha256_file(path) != expected_hash
        ):
            errors.append(f"file_tamper:{relative}")
    if any(
        not isinstance(check, dict) or check.get("status") != "passed" or not check.get("check_id")
        for check in checks
    ):
        errors.append("checks_not_passed")
    if manifest.get("content_digest_sha256") != canonical_sha256(files):
        errors.append("content_digest_sha256")
    if manifest.get("check_digest_sha256") != canonical_sha256(checks):
        errors.append("check_digest_sha256")
    return errors


def write_or_check_manifest(manifest: dict[str, object], check_manifest: bool) -> Check:
    generated_errors = manifest_errors(manifest)
    if generated_errors:
        return Check(
            "release_manifest",
            "failed",
            "generated manifest: " + ", ".join(generated_errors),
        )
    payload = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if check_manifest:
        if not MANIFEST_PATH.exists():
            return Check("release_manifest", "failed", "manifest missing")
        try:
            existing = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return Check("release_manifest", "failed", f"manifest parse error: {exc}")
        if not isinstance(existing, dict):
            return Check("release_manifest", "failed", "manifest root is not an object")
        existing_errors = manifest_errors(existing)
        if existing_errors:
            return Check(
                "release_manifest",
                "failed",
                "committed manifest tamper/schema failure: " + ", ".join(existing_errors),
            )
        if existing != manifest:
            return Check("release_manifest", "failed", "manifest drift")
        return Check(
            "release_manifest",
            "passed",
            f"schema/tamper check passed; content digest {manifest['content_digest_sha256']}",
        )
    MANIFEST_PATH.write_text(payload, encoding="utf-8", newline="\n")
    return Check(
        "release_manifest",
        "passed",
        f"schema/tamper check passed; wrote {MANIFEST_PATH.relative_to(ROOT)}",
    )


def deterministic_zip_timestamp(timestamp: str) -> tuple[int, int, int, int, int, int]:
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(UTC)
    year = max(1980, parsed.year)
    return (year, parsed.month, parsed.day, parsed.hour, parsed.minute, parsed.second)


def build_package(state: dict[str, object]) -> Check:
    RELEASE_OUTPUT.mkdir(parents=True, exist_ok=True)
    output = RELEASE_OUTPUT / "threadline-reverie-submission.zip"
    stamp = deterministic_zip_timestamp(str(state["commit_timestamp"]))
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in package_files(include_manifest=True):
            relative = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(relative, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    digest = sha256_file(output)
    sidecar = RELEASE_OUTPUT / "threadline-reverie-submission.zip.sha256"
    sidecar.write_text(f"{digest}  {output.name}\n", encoding="ascii", newline="\n")
    return Check("release_package", "passed", f"{output.relative_to(ROOT)} / sha256={digest}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when regenerated Prompt Lab or PDF derivatives drift.",
    )
    parser.add_argument(
        "--check-manifest",
        action="store_true",
        help="Compare, rather than write, the release manifest.",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Permit a draft manifest from a dirty working tree.",
    )
    parser.add_argument(
        "--skip-gates",
        action="store_true",
        help="Skip focused backend/frontend execution gates.",
    )
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend gates only.")
    parser.add_argument(
        "--no-package",
        action="store_true",
        help="Do not write the allowlisted ZIP package.",
    )
    parser.add_argument("--backend-python", default=None)
    parser.add_argument("--pdf-python", default=sys.executable)
    return parser.parse_args()


def default_backend_python() -> str:
    candidate = (
        ROOT / "backend" / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    )
    return str(candidate) if candidate.is_file() else sys.executable


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    state = repository_state()
    checks: list[Check] = []
    if not state["working_tree_clean"] and not args.allow_dirty:
        print(
            f"Release refused: working tree has {state['change_count']} change(s). "
            "Commit the intended release or use --allow-dirty for a clearly marked draft.",
            file=sys.stderr,
        )
        return 2
    backend_python = args.backend_python or default_backend_python()
    checks.extend(
        regenerate_artifacts(
            backend_python=backend_python,
            pdf_python=args.pdf_python,
            check_drift=args.check,
        )
    )
    checks.extend(
        [
            validate_required_files(),
            validate_prompt_lab(),
            validate_live_evaluation_artifacts(),
            validate_diagram(),
            validate_links(),
        ]
    )
    checks.append(
        validate_secrets(
            sorted(
                {
                    *curated_source_files(),
                    *package_files(include_manifest=False),
                },
                key=lambda path: path.relative_to(ROOT).as_posix(),
            )
        )
    )
    if not args.skip_gates:
        checks.extend(focused_gates(backend_python, frontend=not args.skip_frontend))

    manifest = build_manifest(state, checks)
    manifest_check = write_or_check_manifest(manifest, args.check_manifest)
    checks.append(manifest_check)
    if not args.no_package and not args.check and all(check.status == "passed" for check in checks):
        checks.append(build_package(state))

    failed = [check for check in checks if check.status != "passed"]
    print("\nTHREADLINE REVERIE RELEASE SUMMARY")
    for check in checks:
        print(f"{check.status.upper():7} {check.check_id}: {check.detail}")
    if failed:
        print(f"RELEASE FAILED: {len(failed)} check(s) did not pass.", file=sys.stderr)
        return 1
    scope = "DRAFT / DIRTY WORKTREE" if not state["working_tree_clean"] else "CLEAN COMMIT"
    print(f"RELEASE VERIFIED: {scope}; public deployment not claimed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
