"""Run the frozen three-case same-model Reverie comparison.

The command is deliberately opt-in. It records every credential-free provider
request, response, and error atomically and resumes only when the frozen spec,
provider configuration, prompts, schemas, fixtures, and source pins still match.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings
from app.evaluation.reverie_live import (
    ReverieLiveEvaluationRunner,
    assert_environment_matches_spec,
    safe_provider_config,
    sha256_bytes,
)
from app.schemas.reverie_evaluation import load_frozen_live_evaluation_spec

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
DEFAULT_SPEC = BACKEND_ROOT / "fixtures" / "reverie_live_evaluation_v1_1.json"
DEFAULT_OUTPUT = BACKEND_ROOT / "data" / "reverie_live_evaluation_v1_1"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-live-provider", action="store_true")
    parser.add_argument(
        "--max-system-runs",
        type=int,
        default=None,
        help="Stop after N newly attempted system runs; the artifact remains labelled partial.",
    )
    return parser.parse_args()


async def _main() -> int:
    args = _arguments()
    spec_path = args.spec.resolve()
    output = args.out.resolve()
    spec, spec_sha = load_frozen_live_evaluation_spec(
        spec_path,
        repository_root=REPOSITORY_ROOT,
    )
    settings = Settings()
    assert_environment_matches_spec(spec, settings)
    safe_config = safe_provider_config(spec)
    print(f"spec_id={spec.spec_id}")
    print(f"spec_sha256={spec_sha}")
    print(f"cases={len(spec.cases)} repetitions={spec.schedule.repetitions}")
    print(f"provider={safe_config['mode']} model={safe_config['model']}")
    print(
        "retry_policy="
        f"transport:{safe_config['max_transport_retries']} "
        f"schema_repair:{safe_config['max_schema_repair_attempts']} "
        f"concurrency:{safe_config['max_concurrent_calls']}"
    )
    print("credentials_configured=True")
    if args.dry_run:
        print("status=validated_dry_run no_provider_calls=1")
        return 0
    if not args.allow_live_provider:
        raise SystemExit(
            "Refusing live generation without explicit --allow-live-provider. "
            "Use --dry-run to validate without provider calls."
        )
    existing = [
        output / "raw-provider-calls.json",
        output / "run-state.json",
        output / "results.json",
    ]
    if not args.resume and any(path.exists() for path in existing):
        raise SystemExit("Output contains an existing run; pass --resume or choose a new --out.")
    runner = ReverieLiveEvaluationRunner(
        spec=spec,
        spec_path=spec_path.relative_to(REPOSITORY_ROOT),
        spec_sha256=spec_sha,
        settings=settings,
        output_directory=output,
        retry_errors=args.retry_errors,
    )
    artifact = await runner.run(max_system_runs=args.max_system_runs)
    results_sha = sha256_bytes(runner.results_path.read_bytes())
    print(f"status={artifact.status}")
    print(
        f"system_runs={artifact.completed_system_runs}/{artifact.expected_system_runs} "
        f"failed={artifact.failed_system_runs}"
    )
    print(f"results={runner.results_path}")
    print(f"results_sha256={results_sha}")
    print(f"recorder={runner.recorder_path}")
    print(f"recorder_sha256={artifact.recorder_artifact_sha256}")
    return 0 if artifact.status == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
