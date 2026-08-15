"""Phase 10T — live Featherless validation under canonical v3 ground truth.

Runs the frozen 27-incident benchmark (or a targeted subset) through the real
provider, normalizes raw provider keys to canonical field keys, runs the frozen
deterministic engine, and reports metrics under ground_truth_schema='v3'.

Never prints API keys or raw record values. Raw provider outputs are stored
under backend/data/live_runs/<run_id>/ and excluded from console output.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings
from app.providers.openai_compatible import OpenAICompatibleProvider
from app.prompts.loader import load_prompt
from app.providers.openai_compatible import _format_schema_for_prompt
from app.services.field_key_normalizer import format_canonical_keys_for_prompt
from app.schemas.models import (
    ExtractionModelOutput, ExtractedField, Certainty, NormalizedRecord,
)
from app.services.field_key_normalizer import normalize_field_key
from app.services.identity_benchmark import (
    load_benchmark, build_universe_table,
    _make_incident_result, _add_structured_pairs, calculate_metrics,
    identity_assignment_sha256, load_identity_assignments,
    RECORD_EXPECTED_FIELDS,
)

SETTINGS = Settings()

TARGETED_INCIDENTS = [
    "INC-CLEAR-MATCH-GOV-ID",
    "INC-CLEAR-MATCH-TRANSLITERATION",
    "INC-CLEAR-NONMATCH-DIFFERENT-IDS",
    "INC-CONFLICTING-EXACT-AGE",
    "INC-CANDIDATE-MISSED-BY-ONE-STRATEGY",
    "INC-PATHOLOGICAL-COMMON-NAME",
    "INC-OCR-NOISE",
    "INC-PHONE-FORMAT-VARIATION",
]

MODE_INCIDENTS = {
    "targeted": TARGETED_INCIDENTS,
    "full": None,  # all incidents
}


def sanitized_cfg() -> dict:
    return {
        "provider": SETTINGS.provider_mode,
        "base_url": SETTINGS.openai_base_url,
        "model": SETTINGS.openai_model,
        "temperature": SETTINGS.llm_temperature,
        "timeout_seconds": SETTINGS.llm_timeout_seconds,
        "max_retries": SETTINGS.llm_max_retries,
        "ground_truth_schema": "v3",
        "api_key_present": bool(SETTINGS.openai_api_key),
    }


def fixture_sha256() -> str:
    p = Path(__file__).resolve().parent.parent / "fixtures" / "identity_benchmark.json"
    return hashlib.sha256(p.read_bytes()).hexdigest()


def make_provider() -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        base_url=SETTINGS.openai_base_url,
        api_key=SETTINGS.openai_api_key or "",
        model=SETTINGS.openai_model,
        temperature=SETTINGS.llm_temperature,
        timeout_seconds=SETTINGS.llm_timeout_seconds,
        max_retries=SETTINGS.llm_max_retries,
    )


async def extract_record(provider, system_prompt: str, inc: dict, rec: dict) -> dict:
    """One live extraction. Returns diagnostics + raw output (never printed)."""
    entry = {
        "incident_id": inc["incident_id"],
        "record_id": rec["record_id"],
        "status": "error",
        "latency_ms": 0,
        "attempts": 0,
        "tokens": None,
        "error_class": None,
        "error_preview": None,
        "fields": [],          # canonical ExtractedField-compatible list
        "unknown_keys": [],    # (raw_key, reason_code)
        "raw_output": None,    # preserved for secure artifact storage
    }
    user_prompt = (
        f"<untrusted_evidence record_id={rec['record_id']!r}>\n"
        f"{rec['text']}\n</untrusted_evidence>"
    )
    started = perf_counter()
    try:
        pr = await provider.generate_structured(
            template_id="extraction",
            template_version="v1",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=ExtractionModelOutput,
            mock_payload={},
        )
        entry["latency_ms"] = round((perf_counter() - started) * 1000)
        entry["status"] = "ok"
        entry["attempts"] = pr.metadata.attempts
        entry["tokens"] = pr.metadata.token_usage
        entry["model"] = pr.metadata.model
        entry["raw_output"] = {
            "keys": [f.key for f in pr.output.fields],
            "values": {f.key: f.value for f in pr.output.fields},
            "certainties": {f.key: f.certainty.value for f in pr.output.fields},
        }
        for f in pr.output.fields:
            nk = normalize_field_key(f.key)
            if nk.canonical_key is not None:
                entry["fields"].append({
                    "key": nk.canonical_key.value,
                    "value": f.value,
                    "certainty": f.certainty.value,
                    "normalization_status": nk.status.value,
                    "normalization_rule_id": nk.normalization_rule_id,
                })
            else:
                entry["unknown_keys"].append((f.key, nk.reason_code))
    except Exception as exc:
        entry["latency_ms"] = round((perf_counter() - started) * 1000)
        entry["error_class"] = type(exc).__name__
        entry["error_preview"] = str(exc)[:300]
        entry["status"] = "error"
    return entry


def build_record(rec: dict, extraction: dict) -> NormalizedRecord:
    """Build a NormalizedRecord with canonical keys only."""
    fields = []
    for f in extraction.get("fields", []):
        try:
            certainty = Certainty(f["certainty"])
        except ValueError:
            certainty = Certainty.estimated
        fields.append(ExtractedField(
            field_id=f'{rec["record_id"]}-{f["key"]}',
            key=f["key"],
            label=f["key"],
            value=f["value"],
            certainty=certainty,
            source_span_id=f'{rec["record_id"]}-{f["key"]}-live',
        ))
    return NormalizedRecord(
        record_id=rec["record_id"],
        source_type=rec.get("source_type", "unknown"),
        language=rec.get("language", "English"),
        text=rec.get("text", ""),
        display_name=rec.get("display_name", rec["record_id"]),
        safe_text=rec.get("text", ""),
        fields=fields,
    )


def subset_assignments(incidents: list[dict]) -> dict[str, str | None]:
    """Filter full v3 identity assignments to the selected incidents only.

    The v3 cover-check requires a 1:1 match between assignments and fixture
    records, so subset runs must pass a subset-filtered assignment dict.
    """
    full = load_identity_assignments()
    subset_ids = {
        r["record_id"] for inc in incidents for r in inc["records"]
    }
    return {rid: fid for rid, fid in full.items() if rid in subset_ids}


def load_checkpoint(run_dir: Path) -> dict[str, dict]:
    """Load previously completed extraction entries for resume support."""
    raw_path = run_dir / "raw-outputs.json"
    if not raw_path.exists():
        return {}
    try:
        blob = json.loads(raw_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    records = blob.get("records", {})
    return {rid: e for rid, e in records.items() if e.get("status") == "ok"}


def _write_checkpoint(run_dir: Path, run_id: str, extraction_map: dict[str, dict]) -> None:
    """Persist current extraction state so interrupted runs can resume."""
    raw_path = run_dir / "raw-outputs.json"
    blob = {
        "run_id": run_id,
        "model": SETTINGS.openai_model,
        "timestamp": time.time(),
        "records": {
            rid: {
                "status": e["status"],
                "latency_ms": e["latency_ms"],
                "attempts": e["attempts"],
                "tokens": e["tokens"],
                "error_class": e["error_class"],
                "error_preview": e["error_preview"],
                "fields": e["fields"],
                "unknown_keys": e["unknown_keys"],
                "raw_output": e["raw_output"],
            }
            for rid, e in extraction_map.items()
        },
    }
    raw_path.write_text(json.dumps(blob, indent=2, default=str), encoding="utf-8")


async def run_live_pass(
    provider, system_prompt: str, incidents: list[dict], run_id: str, out_root: Path,
) -> dict:
    """One full live pass over the selected incidents. Returns run results."""
    # ── 0. v3 identity assignments scoped to this incident set ──
    assignments = subset_assignments(incidents)
    # ── 1. Extract all records (sequential; provider semaphore = 1), with
    #        checkpoint/resume so the pass can survive process restarts. ──
    run_dir = out_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    extraction_map: dict[str, dict] = load_checkpoint(run_dir)
    pending = [
        (inc, rec) for inc in incidents for rec in inc["records"]
        if rec["record_id"] not in extraction_map
    ]
    for inc, rec in pending:
        entry = await extract_record(provider, system_prompt, inc, rec)
        extraction_map[rec["record_id"]] = entry
        # Incremental checkpoint after every record
        _write_checkpoint(run_dir, run_id, extraction_map)

    # ── 2. Build incident results through the frozen engine ──
    incident_results = []
    for inc in incidents:
        ir = _make_incident_result(inc)
        records = [build_record(r, extraction_map[r["record_id"]]) for r in inc["records"]]
        _add_structured_pairs(ir, records, inc, "live_featherless")
        incident_results.append(ir)

    # ── 3. Metrics under v3 ──
    metrics = calculate_metrics(
        incident_results, incidents,
        system="live_featherless", ground_truth_schema="v3",
        identity_assignments=assignments,
    )
    universe = build_universe_table(
        incidents, ground_truth_schema="v3",
        identity_assignments=assignments,
    )

    # ── 4. Per-incident + per-pair diagnostics ──
    pair_rows = []
    pair_truth = {
        (u.incident_id, frozenset({u.record_a, u.record_b})): u
        for u in universe
    }
    for ir in incident_results:
        for pr in ir.pair_results:
            key = (ir.incident_id, frozenset({pr.record_id_a, pr.record_id_b}))
            u = pair_truth.get(key)
            pair_rows.append({
                "incident": ir.incident_id,
                "pair": f"{pr.record_id_a}<->{pr.record_id_b}",
                "identity_truth": u.identity_truth if u else "unlabeled",
                "evidence_disposition": u.evidence_disposition if u else "",
                "candidate_generation_rules": pr.candidate_generation_rules,
                "linkage_state": pr.linkage_state,
                "total_score": round(pr.total_score, 4),
                "blocking_conflicts": pr.blocking_conflicts,
                "supporting_fields": pr.supporting_fields,
                "expected_pair_match": pr.expected_pair_match,
            })

    # Safety gate flags for this pass
    safety = {
        "different_identity_auto_links": metrics.false_merge_count,
        "under_specified_auto_links": metrics.unsafe_under_specified_link_count,
        "blocked_conflict_recall": metrics.blocked_conflict_recall,
        "malformed_output_escapes": sum(
            1 for e in extraction_map.values()
            if e["status"] == "error"
        ),
        "retrieval_fn": metrics.same_identity_candidate_recall_d
            - metrics.same_identity_candidate_recall_n,
    }

    return {
        "run_id": run_id,
        "extraction": {
            "total": len(extraction_map),
            "ok": sum(1 for e in extraction_map.values() if e["status"] == "ok"),
            "errors": sum(1 for e in extraction_map.values() if e["status"] == "error"),
            "error_classes": dict(Counter(
                e["error_class"] for e in extraction_map.values() if e["status"] == "error"
            )),
            "unknown_key_count": sum(len(e["unknown_keys"]) for e in extraction_map.values()),
            "avg_latency_ms": round(sum(
                e["latency_ms"] for e in extraction_map.values()
            ) / max(len(extraction_map), 1)),
            "max_latency_ms": max(
                (e["latency_ms"] for e in extraction_map.values()), default=0
            ),
            "total_tokens": sum(e["tokens"] or 0 for e in extraction_map.values()),
            "total_attempts": sum(e["attempts"] or 0 for e in extraction_map.values()),
            "canonical_key_validity": sum(
                1 for e in extraction_map.values()
                if e["status"] == "ok"
                and not e["unknown_keys"]
            ) / max(sum(1 for e in extraction_map.values() if e["status"] == "ok"), 1),
            "per_record": {
                rid: {
                    "status": e["status"],
                    "latency_ms": e["latency_ms"],
                    "attempts": e["attempts"],
                    "fields": [f["key"] for f in e["fields"]],
                    "unknown_keys": e["unknown_keys"],
                    "error_class": e["error_class"],
                }
                for rid, e in extraction_map.items()
            },
        },
        "metrics": {
            "evaluated_pairs": metrics.evaluated_pairs,
            "same_identity_pairs": metrics.same_identity_pairs,
            "different_identity_pairs": metrics.different_identity_pairs,
            "under_specified_pairs": metrics.under_specified_pair_count,
            "universe_under_specified": metrics.universe_under_specified_pair_count,
            "decision_state_counts": metrics.decision_state_counts,
            "true_link_count": metrics.true_link_count,
            "false_merge_count": metrics.false_merge_count,
            "false_non_match_count": metrics.false_non_match_count,
            "blocked_conflict_recall": metrics.blocked_conflict_recall,
            "human_review": metrics.human_review_required_count,
            "insufficient": metrics.insufficient_evidence_count,
            "blocked": metrics.blocked_by_conflict_count,
            "wss": metrics.weighted_safety_score,
            "wss_v3": metrics.wss_v3,
            "unsafe_under_specified_link_count": metrics.unsafe_under_specified_link_count,
        },
        # Universe-grounded retrieval recall (system-agnostic; the candidate-
        # generation block in the frozen metrics module is gated to
        # structured_engine/mock_extraction and stays untouched for live runs).
        "retrieval": {
            "tp": metrics.same_identity_candidate_recall_n,
            "denominator": metrics.same_identity_candidate_recall_d,
            "fn": metrics.same_identity_candidate_recall_d
                - metrics.same_identity_candidate_recall_n,
            "recall": metrics.same_identity_candidate_recall,
        },
        "safety": safety,
        "pair_rows": pair_rows,
    }


def build_live_artifact(
    run: dict, incidents: list[dict], *, execution_mode: str = "live_provider",
) -> dict:
    """Full provenance artifact for one live pass (or the mock comparison)."""
    assignments = load_identity_assignments()
    return {
        "execution_mode": execution_mode,
        "benchmark_version": "IDENTITY-BENCH-v1",
        "fixture_sha256": fixture_sha256(),
        "ground_truth_schema": "v3",
        "identity_schema_version": "1.0",
        "identity_assignment_sha256": identity_assignment_sha256(assignments),
        "provider": SETTINGS.provider_mode,
        "model": SETTINGS.openai_model,
        "temperature": SETTINGS.llm_temperature,
        "run_id": run.get("run_id"),
        "timestamp": time.time(),
        "incidents": [i["incident_id"] for i in incidents],
        "incident_count": len(incidents),
        "metrics": run.get("metrics"),
        "safety": run.get("safety"),
        "extraction_summary": {
            k: v for k, v in run.get("extraction", {}).items()
            if k != "per_record"
        },
    }


async def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["targeted", "full"], default="targeted")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--out", default="data/live_runs")
    args = parser.parse_args()

    incidents = load_benchmark()
    if args.mode == "targeted":
        incidents = [i for i in incidents if i["incident_id"] in TARGETED_INCIDENTS]

    print("=" * 72)
    print("PHASE 10T — LIVE FEATHERLESS VALIDATION (v3)")
    print("=" * 72)
    cfg = sanitized_cfg()
    print(f"mode: {args.mode} ({len(incidents)} incidents)")
    print(f"model: {cfg['model']}")
    print(f"base_url: {cfg['base_url']}")
    print(f"temperature: {cfg['temperature']}")
    print(f"timeout: {cfg['timeout_seconds']}s max_retries: {cfg['max_retries']}")
    print(f"ground_truth_schema: {cfg['ground_truth_schema']}")
    print(f"fixture_sha256: {fixture_sha256()}")
    assignments = load_identity_assignments()
    print(f"identity_assignment_sha256: {identity_assignment_sha256(assignments)}")
    print()

    template = load_prompt("extraction", "v1")
    schema_block = _format_schema_for_prompt(ExtractionModelOutput.model_json_schema())
    canonical_keys_block = format_canonical_keys_for_prompt()
    NL = chr(10)
    system_prompt = template.content + NL + NL + canonical_keys_block + NL + NL + schema_block
    provider = make_provider()
    out_root = Path(__file__).resolve().parent.parent / args.out

    runs = []
    for i in range(1, args.runs + 1):
        run_id = f"{args.mode}-run-{i}"
        print(f"--- {run_id} ---")
        started = perf_counter()
        run = await run_live_pass(provider, system_prompt, incidents, run_id, out_root)
        run["duration_s"] = round(perf_counter() - started)
        runs.append(run)

        ext = run["extraction"]
        m = run["metrics"]
        print(f"  extraction: {ext['ok']}/{ext['total']} ok, "
              f"avg {ext['avg_latency_ms']}ms, tokens {ext['total_tokens']}")
        print(f"  unknown keys: {ext['unknown_key_count']}")
        print(f"  evaluated: {m['evaluated_pairs']}  true links: {m['true_link_count']}  "
              f"false merges: {m['false_merge_count']}  FNL: {m['false_non_match_count']}")
        print(f"  decisions: {m['decision_state_counts']}  WSS: {m['wss']}")
        print(f"  blocked conflict recall: {m['blocked_conflict_recall']:.3f}  "
              f"unsafe under-links: {m['unsafe_under_specified_link_count']}")
        print()

        # Per-incident table
        print("  per-incident:")
        print(f"    {'incident':<38} {'truth':<9} {'state':<26} {'score':>6}")
        for ir_id in [i["incident_id"] for i in incidents]:
            row = run["pair_rows"]
            inc_rows = [r for r in row if r["incident"] == ir_id]
            # rank-1 by score
            if not inc_rows:
                print(f"    {ir_id:<38} {'—':<9} {'no candidates':<26} {'—':>6}")
                continue
            top = sorted(inc_rows, key=lambda r: r["total_score"], reverse=True)[0]
            print(f"    {ir_id:<38} {top['identity_truth']:<9} "
                  f"{top['linkage_state']:<26} {top['total_score']:>6.3f}")

        # Save live artifact per run
        artifact = build_live_artifact(run, incidents, execution_mode="live_provider")
        art_path = out_root / run_id / "live-artifact.json"
        art_path.parent.mkdir(parents=True, exist_ok=True)
        art_path.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")
        art_hash = hashlib.sha256(art_path.read_bytes()).hexdigest()[:16]
        print(f"  artifact: {art_path} sha256[:16]={art_hash}")

        # Per-run safety gate
        s = run["safety"]
        print("  safety gates:")
        print(f"    different-id auto-links: {s['different_identity_auto_links']} "
              f"(must be 0)")
        print(f"    under-specified auto-links: {s['under_specified_auto_links']} "
              f"(must be 0)")
        print(f"    blocked conflict recall: {s['blocked_conflict_recall']:.3f} "
              f"(must be 1.0)")
        print(f"    extraction errors: {s['malformed_output_escapes']}")
        print()

    # ── Aggregate across runs ──
    if len(runs) > 1:
        print("=" * 72)
        print("RUN AGGREGATION")
        for metric in ["true_link_count", "false_merge_count", "false_non_match_count",
                       "human_review", "insufficient", "blocked", "wss"]:
            vals = [r["metrics"][metric] for r in runs]
            mean = sum(vals) / len(vals)
            print(f"  {metric:<28} min={min(vals):>6} mean={mean:>8.2f} max={max(vals):>6}")
        fm_runs = [r["metrics"]["false_merge_count"] for r in runs]
        unsafe_runs = [r["metrics"]["unsafe_under_specified_link_count"] for r in runs]
        print(f"  false-merge safety: {'PASS' if all(v == 0 for v in fm_runs) else 'FAILED'}")
        print(f"  under-specified safety: "
              f"{'PASS' if all(v == 0 for v in unsafe_runs) else 'FAILED'}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
