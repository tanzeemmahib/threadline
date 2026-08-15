"""Phase 11 — live Prompt V1 vs V2 A/B validation under canonical v3 ground truth.

Minimal fork of live_phase10t_runner.py that adds --prompt v1|v2, saves to
data/live_runs_phase11/, and reports extraction-quality metrics alongside
linkage metrics for A/B comparison.
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
from app.prompts.loader import load_prompt
from app.providers.openai_compatible import OpenAICompatibleProvider, _format_schema_for_prompt
from app.schemas.models import (
    Certainty,
    ExtractedField,
    ExtractionModelOutput,
    NormalizedRecord,
)
from app.services.field_key_normalizer import format_canonical_keys_for_prompt, normalize_field_key
from app.services.identity_benchmark import (
    RECORD_EXPECTED_FIELDS,
    _add_structured_pairs,
    _make_incident_result,
    build_universe_table,
    calculate_metrics,
    identity_assignment_sha256,
    load_benchmark,
    load_identity_assignments,
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

ALL_CANONICAL_KEYS = sorted(RECORD_EXPECTED_FIELDS["GOV-A1"]
    | RECORD_EXPECTED_FIELDS["MULTI-A1"]
    | RECORD_EXPECTED_FIELDS["SIB-A1"]
    | RECORD_EXPECTED_FIELDS["TRANS-A1"]
    | RECORD_EXPECTED_FIELDS["DUP-A1"]
    | {"email", "language", "aliases", "family_member_names", "shelter", "timeline_event"})


def sanitized_cfg() -> dict:
    return {
        "provider": SETTINGS.provider_mode,
        "base_url": SETTINGS.openai_base_url,
        "model": SETTINGS.openai_model,
        "temperature": SETTINGS.llm_temperature,
        "timeout_seconds": SETTINGS.llm_timeout_seconds,
        "max_retries": SETTINGS.llm_max_retries,
        "max_concurrent_calls": SETTINGS.llm_max_concurrent_calls,
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


async def extract_record(provider, system_prompt: str, prompt_version: str,
                         inc: dict, rec: dict) -> dict:
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
        "fields": [],
        "unknown_keys": [],
        "raw_output": None,
    }
    user_prompt = (
        f"<untrusted_evidence record_id={rec['record_id']!r}>\n"
        f"{rec['text']}\n</untrusted_evidence>"
    )
    started = perf_counter()
    try:
        pr = await provider.generate_structured(
            template_id="extraction",
            template_version=prompt_version,
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
    full = load_identity_assignments()
    subset_ids = {r["record_id"] for inc in incidents for r in inc["records"]}
    return {rid: fid for rid, fid in full.items() if rid in subset_ids}


def load_checkpoint(run_dir: Path) -> dict[str, dict]:
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


# ── Extraction-quality metrics (Phase 11B style) ──

def compute_extraction_quality(extraction_map: dict[str, dict],
                               incidents: list[dict]) -> dict:
    """Compute per-field extraction recall/precision using RECORD_EXPECTED_FIELDS."""
    per_field: dict[str, dict] = {}
    for key in ALL_CANONICAL_KEYS:
        per_field[key] = {"tp": 0, "fp": 0, "fn": 0, "expected": 0, "extracted": 0}

    total_tp = total_fp = total_fn = 0
    hallucinated = 0
    unknown_total = 0

    for inc in incidents:
        for rec in inc["records"]:
            rid = rec["record_id"]
            expected = RECORD_EXPECTED_FIELDS.get(rid, set())
            e = extraction_map.get(rid, {})
            extracted_keys = {f["key"] for f in e.get("fields", [])}
            unknown_total += len(e.get("unknown_keys", []))

            for key in ALL_CANONICAL_KEYS:
                in_expected = key in expected
                in_extracted = key in extracted_keys
                if in_expected:
                    per_field[key]["expected"] += 1
                if in_extracted:
                    per_field[key]["extracted"] += 1
                if in_expected and in_extracted:
                    per_field[key]["tp"] += 1
                    total_tp += 1
                elif in_expected and not in_extracted:
                    per_field[key]["fn"] += 1
                    total_fn += 1
                elif not in_expected and in_extracted:
                    per_field[key]["fp"] += 1
                    total_fp += 1
                    hallucinated += 1

    field_results = {}
    for key, counts in per_field.items():
        tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        if counts["expected"] > 0 or counts["extracted"] > 0:
            field_results[key] = {
                "expected": counts["expected"], "extracted": counts["extracted"],
                "tp": tp, "fp": fp, "fn": fn,
                "precision": round(precision, 4), "recall": round(recall, 4),
                "f1": round(f1, 4),
            }

    micro_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1 = (2 * micro_precision * micro_recall / (micro_precision + micro_recall)
                if (micro_precision + micro_recall) > 0 else 0.0)

    return {
        "total_tp": total_tp, "total_fp": total_fp, "total_fn": total_fn,
        "hallucinated_fields": hallucinated,
        "unknown_key_count": unknown_total,
        "micro_precision": round(micro_precision, 4),
        "micro_recall": round(micro_recall, 4),
        "micro_f1": round(micro_f1, 4),
        "records_ok": sum(1 for e in extraction_map.values() if e["status"] == "ok"),
        "records_total": len(extraction_map),
        "per_field": field_results,
    }


async def run_live_pass(
    provider, system_prompt: str, prompt_version: str,
    incidents: list[dict], run_id: str, out_root: Path, *, retry_errors: bool = False,
) -> dict:
    assignments = subset_assignments(incidents)
    run_dir = out_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    extraction_map: dict[str, dict] = load_checkpoint(run_dir)
    pending = [
        (inc, rec) for inc in incidents for rec in inc["records"]
        if rec["record_id"] not in extraction_map
        or (retry_errors and extraction_map[rec["record_id"]].get("status") == "error")
    ]
    semaphore = asyncio.Semaphore(max(1, SETTINGS.llm_max_concurrent_calls))
    checkpoint_lock = asyncio.Lock()

    async def extract_and_checkpoint(inc: dict, rec: dict) -> None:
        async with semaphore:
            entry = await extract_record(provider, system_prompt, prompt_version, inc, rec)
        async with checkpoint_lock:
            extraction_map[rec["record_id"]] = entry
            _write_checkpoint(run_dir, run_id, extraction_map)

    await asyncio.gather(*(extract_and_checkpoint(inc, rec) for inc, rec in pending))

    incident_results = []
    for inc in incidents:
        ir = _make_incident_result(inc)
        records = [build_record(r, extraction_map[r["record_id"]]) for r in inc["records"]]
        _add_structured_pairs(ir, records, inc, "live_featherless")
        incident_results.append(ir)

    metrics = calculate_metrics(
        incident_results, incidents,
        system="live_featherless", ground_truth_schema="v3",
        identity_assignments=assignments,
    )
    universe = build_universe_table(
        incidents, ground_truth_schema="v3",
        identity_assignments=assignments,
    )

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

    safety = {
        "different_identity_auto_links": metrics.false_merge_count,
        "under_specified_auto_links": metrics.unsafe_under_specified_link_count,
        "blocked_conflict_recall": metrics.blocked_conflict_recall,
        "malformed_output_escapes": sum(
            1 for e in extraction_map.values() if e["status"] == "error"
        ),
    }

    extraction_quality = compute_extraction_quality(extraction_map, incidents)

    return {
        "run_id": run_id,
        "prompt_version": prompt_version,
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
        },
        "extraction_quality": extraction_quality,
        "metrics": {
            "evaluated_pairs": metrics.evaluated_pairs,
            "same_identity_pairs": metrics.same_identity_pairs,
            "different_identity_pairs": metrics.different_identity_pairs,
            "decision_state_counts": metrics.decision_state_counts,
            "true_link_count": metrics.true_link_count,
            "false_merge_count": metrics.false_merge_count,
            "false_non_match_count": metrics.false_non_match_count,
            "blocked_conflict_recall": metrics.blocked_conflict_recall,
            "human_review": metrics.human_review_required_count,
            "insufficient": metrics.insufficient_evidence_count,
            "blocked": metrics.blocked_by_conflict_count,
            "wss": metrics.weighted_safety_score,
            "unsafe_under_specified_link_count": metrics.unsafe_under_specified_link_count,
        },
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


def build_live_artifact(run: dict, incidents: list[dict], prompt_version: str) -> dict:
    assignments = load_identity_assignments()
    return {
        "execution_mode": "live_provider",
        "benchmark_version": "IDENTITY-BENCH-v1",
        "fixture_sha256": fixture_sha256(),
        "ground_truth_schema": "v3",
        "identity_assignment_sha256": identity_assignment_sha256(assignments),
        "provider": SETTINGS.provider_mode,
        "model": SETTINGS.openai_model,
        "temperature": SETTINGS.llm_temperature,
        "prompt_version": prompt_version,
        "run_id": run.get("run_id"),
        "timestamp": time.time(),
        "incidents": [i["incident_id"] for i in incidents],
        "incident_count": len(incidents),
        "metrics": run.get("metrics"),
        "extraction_quality": run.get("extraction_quality"),
        "safety": run.get("safety"),
    }


# ── A/B comparison report ──

def print_ab_comparison(run_v1: dict, run_v2: dict) -> None:
    """Print side-by-side extraction-quality and linkage comparison."""
    print()
    print("=" * 78)
    print("PHASE 11 A/B: PROMPT V1 vs V2 — COMPARISON")
    print("=" * 78)

    eq1 = run_v1.get("extraction_quality", {})
    eq2 = run_v2.get("extraction_quality", {})
    m1 = run_v1["metrics"]
    m2 = run_v2["metrics"]

    # Extraction quality comparison
    print("\n--- Extraction-Quality Metrics ---")
    print(f"{'Metric':<30} {'V1':>12} {'V2':>12} {'Delta':>12}")
    print("-" * 66)
    for label, k1, k2 in [
        ("micro recall", eq1.get("micro_recall", 0), eq2.get("micro_recall", 0)),
        ("micro precision", eq1.get("micro_precision", 0), eq2.get("micro_precision", 0)),
        ("micro F1", eq1.get("micro_f1", 0), eq2.get("micro_f1", 0)),
        ("hallucinated fields", eq1.get("hallucinated_fields", 0), eq2.get("hallucinated_fields", 0)),
        ("unknown keys", eq1.get("unknown_key_count", 0), eq2.get("unknown_key_count", 0)),
        ("extraction success", f"{eq1.get('records_ok',0)}/{eq1.get('records_total',0)}",
         f"{eq2.get('records_ok',0)}/{eq2.get('records_total',0)}"),
    ]:
        if isinstance(k1, str):
            print(f"{label:<30} {k1:>12} {k2:>12}")
            continue
        d = k2 - k1
        print(f"{label:<30} {k1:>12.4f} {k2:>12.4f} {d:>+12.4f}")

    # Per-field recall
    print("\n--- Per-Field Recall ---")
    fields_v1 = eq1.get("per_field", {})
    fields_v2 = eq2.get("per_field", {})
    all_fields = sorted(set(fields_v1) | set(fields_v2))
    print(f"{'Field':<28} {'V1 Recall':>10} {'V2 Recall':>10} {'Delta':>10}")
    print("-" * 58)
    for f in all_fields:
        r1 = fields_v1.get(f, {}).get("recall", 0)
        r2 = fields_v2.get(f, {}).get("recall", 0)
        if r1 == 0 and r2 == 0:
            continue
        d = r2 - r1
        marker = " <<<" if abs(d) > 0.05 else ""
        print(f"{f:<28} {r1:>10.4f} {r2:>10.4f} {d:>+10.4f}{marker}")

    # Linkage metrics
    print("\n--- Linkage Metrics ---")
    print(f"{'Metric':<30} {'V1':>12} {'V2':>12} {'Delta':>12}")
    print("-" * 66)
    for label, k1, k2 in [
        ("evaluated pairs", m1["evaluated_pairs"], m2["evaluated_pairs"]),
        ("true links", m1["true_link_count"], m2["true_link_count"]),
        ("false merges", m1["false_merge_count"], m2["false_merge_count"]),
        ("false non-links", m1["false_non_match_count"], m2["false_non_match_count"]),
        ("human review", m1["human_review"], m2["human_review"]),
        ("insufficient evidence", m1["insufficient"], m2["insufficient"]),
        ("blocked by conflict", m1["blocked"], m2["blocked"]),
        ("WSS", m1["wss"], m2["wss"]),
        ("conflict recall", m1["blocked_conflict_recall"], m2["blocked_conflict_recall"]),
        ("unsafe links", m1["unsafe_under_specified_link_count"], m2["unsafe_under_specified_link_count"]),
    ]:
        if isinstance(k1, float):
            d = k2 - k1
            print(f"{label:<30} {k1:>12.4f} {k2:>12.4f} {d:>+12.4f}")
        else:
            print(f"{label:<30} {k1:>12} {k2:>12}")

    # Pair-by-pair changes
    print("\n--- Pair-Level Changes ---")
    p1 = {(r["incident"], r["pair"]): r for r in run_v1.get("pair_rows", [])}
    p2 = {(r["incident"], r["pair"]): r for r in run_v2.get("pair_rows", [])}
    changed = []
    for key in set(p1) | set(p2):
        r1 = p1.get(key, {})
        r2 = p2.get(key, {})
        s1 = r1.get("total_score", 0)
        s2 = r2.get("total_score", 0)
        st1 = r1.get("linkage_state", "—")
        st2 = r2.get("linkage_state", "—")
        if abs(s2 - s1) > 0.001 or st1 != st2:
            changed.append((key, r1, r2, s1, s2, st1, st2))
    if changed:
        print(f"{'Incident':<36} {'Pair':<18} {'V1->V2 Score':>14} {'V1->V2 State':>30}")
        print("-" * 100)
        for (inc, pair), _r1, _r2, s1, s2, st1, st2 in sorted(changed):
            print(f"{inc:<36} {pair:<18} {s1:.4f} -> {s2:.4f}   {st1} -> {st2}")
    else:
        print("  (no pairs changed score or state)")


async def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["targeted", "full"], default="targeted")
    parser.add_argument("--prompt", choices=["v1", "v2", "v3"], required=True)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--out", default="data/live_runs_phase11")
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Reuse successful checkpoints and retry only records saved with error status.",
    )
    args = parser.parse_args()

    incidents = load_benchmark()
    if args.mode == "targeted":
        incidents = [i for i in incidents if i["incident_id"] in TARGETED_INCIDENTS]

    prompt_version = args.prompt
    print("=" * 72)
    print(f"PHASE 11 — LIVE PROMPT {prompt_version.upper()} VALIDATION (v3)")
    print("=" * 72)
    cfg = sanitized_cfg()
    print(f"mode: {args.mode} ({len(incidents)} incidents)")
    print(f"prompt: {prompt_version}")
    print(f"model: {cfg['model']}")
    print(f"base_url: {cfg['base_url']}")
    print(f"temperature: {cfg['temperature']}")
    print(f"timeout: {cfg['timeout_seconds']}s max_retries: {cfg['max_retries']}")
    print(f"max_concurrent_calls: {cfg['max_concurrent_calls']}")
    print(f"fixture_sha256: {fixture_sha256()}")
    assignments = load_identity_assignments()
    print(f"identity_assignment_sha256: {identity_assignment_sha256(assignments)}")
    print()

    template = load_prompt("extraction", prompt_version)
    schema_block = _format_schema_for_prompt(ExtractionModelOutput.model_json_schema())
    canonical_keys_block = format_canonical_keys_for_prompt()
    NL = chr(10)
    system_prompt = template.content + NL + NL + canonical_keys_block + NL + NL + schema_block
    provider = make_provider()
    out_root = Path(__file__).resolve().parent.parent / args.out

    runs = []
    for i in range(1, args.runs + 1):
        run_id = f"{args.mode}-prompt-{prompt_version}-run-{i}"
        print(f"--- {run_id} ---")
        started = perf_counter()
        run = await run_live_pass(provider, system_prompt, prompt_version,
                                  incidents, run_id, out_root,
                                  retry_errors=args.retry_errors)
        run["duration_s"] = round(perf_counter() - started)
        runs.append(run)

        ext = run["extraction"]
        eq = run.get("extraction_quality", {})
        m = run["metrics"]
        print(f"  extraction: {ext['ok']}/{ext['total']} ok, "
              f"avg {ext['avg_latency_ms']}ms, tokens {ext['total_tokens']}")
        print(f"  extraction quality: recall={eq.get('micro_recall',0):.3f} "
              f"precision={eq.get('micro_precision',0):.3f} "
              f"f1={eq.get('micro_f1',0):.3f}")
        print(f"  unknown keys: {eq.get('unknown_key_count',0)}  "
              f"hallucinated: {eq.get('hallucinated_fields',0)}")
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
            if not inc_rows:
                print(f"    {ir_id:<38} {'—':<9} {'no candidates':<26} {'—':>6}")
                continue
            top = sorted(inc_rows, key=lambda r: r["total_score"], reverse=True)[0]
            print(f"    {ir_id:<38} {top['identity_truth']:<9} "
                  f"{top['linkage_state']:<26} {top['total_score']:>6.3f}")

        # Save live artifact
        artifact = build_live_artifact(run, incidents, prompt_version)
        art_path = out_root / run_id / "live-artifact.json"
        art_path.parent.mkdir(parents=True, exist_ok=True)
        art_path.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")
        art_hash = hashlib.sha256(art_path.read_bytes()).hexdigest()[:16]
        print(f"  artifact: {art_path} sha256[:16]={art_hash}")

        # Safety gate
        s = run["safety"]
        print("  safety gates:")
        print(f"    different-id auto-links: {s['different_identity_auto_links']} (must be 0)")
        print(f"    under-specified auto-links: {s['under_specified_auto_links']} (must be 0)")
        print(f"    blocked conflict recall: {s['blocked_conflict_recall']:.3f} (must be 1.0)")
        print(f"    extraction errors: {s['malformed_output_escapes']}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
