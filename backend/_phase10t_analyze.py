"""Phase 10T — replay cached live outputs through the frozen engine.

Reads backend/data/live_runs/<run_id>/raw-outputs.json and recomputes the
pair-level results, earliest-divergence analysis, and mock-vs-live comparison
without making any provider calls.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.identity_benchmark import (
    load_benchmark, mock_extract_fields, build_universe_table,
    _make_incident_result, _add_structured_pairs, calculate_metrics,
    RECORD_EXPECTED_FIELDS,
)
from app.schemas.models import NormalizedRecord, ExtractedField, Certainty
from app.services.field_key_normalizer import normalize_field_key
from scripts.live_phase10t_runner import TARGETED_INCIDENTS, subset_assignments, build_record


def load_cached(run_dir: Path) -> dict[str, dict]:
    raw = json.loads((run_dir / "raw-outputs.json").read_text(encoding="utf-8"))
    return raw["records"]


def mock_records(incidents: list[dict]) -> dict[str, NormalizedRecord]:
    out = {}
    for inc in incidents:
        for r in inc["records"]:
            fields = mock_extract_fields(r["text"], r["record_id"], r.get("language", "English"))
            out[r["record_id"]] = NormalizedRecord(
                record_id=r["record_id"], source_type=r.get("source_type", "unknown"),
                language=r.get("language", "English"), text=r.get("text", ""),
                display_name=r["record_id"], safe_text=r.get("text", ""), fields=fields,
            )
    return out


def replay(incidents: list[dict], extraction_map: dict[str, dict], system: str) -> dict:
    assignments = subset_assignments(incidents)
    incident_results = []
    for inc in incidents:
        ir = _make_incident_result(inc)
        if system == "live":
            records = [build_record(r, extraction_map[r["record_id"]]) for r in inc["records"]]
        else:
            records = [mock_records(incidents)[r["record_id"]] for r in inc["records"]]
        _add_structured_pairs(ir, records, inc, system)
        incident_results.append(ir)
    metrics = calculate_metrics(
        incident_results, incidents, system=system,
        ground_truth_schema="v3", identity_assignments=assignments,
    )
    universe = build_universe_table(incidents, ground_truth_schema="v3",
                                    identity_assignments=assignments)
    pair_truth = {(u.incident_id, frozenset({u.record_a, u.record_b})): u for u in universe}
    rows = []
    for ir in incident_results:
        for pr in ir.pair_results:
            key = (ir.incident_id, frozenset({pr.record_id_a, pr.record_id_b}))
            u = pair_truth.get(key)
            rows.append({
                "incident": ir.incident_id,
                "pair": f"{pr.record_id_a}<->{pr.record_id_b}",
                "identity_truth": u.identity_truth if u else "unlabeled",
                "evidence_disposition": u.evidence_disposition if u else "",
                "candidate_found": pr.candidate_found,
                "rules": pr.candidate_generation_rules,
                "state": pr.linkage_state,
                "score": round(pr.total_score, 4),
                "conflicts": pr.blocking_conflicts,
                "supporting": pr.supporting_fields,
            })
    return {
        "metrics": {
            "evaluated": metrics.evaluated_pairs,
            "same": metrics.same_identity_pairs,
            "diff": metrics.different_identity_pairs,
            "under": metrics.under_specified_pair_count,
            "decisions": metrics.decision_state_counts,
            "true_links": metrics.true_link_count,
            "false_merges": metrics.false_merge_count,
            "fnl": metrics.false_non_match_count,
            "blocked_conflict_recall": metrics.blocked_conflict_recall,
            "human_review": metrics.human_review_required_count,
            "insufficient": metrics.insufficient_evidence_count,
            "blocked": metrics.blocked_by_conflict_count,
            "wss": metrics.weighted_safety_score,
            "unsafe_under": metrics.unsafe_under_specified_link_count,
            "retrieval_recall": metrics.same_identity_candidate_recall,
            "retrieval_n": metrics.same_identity_candidate_recall_n,
            "retrieval_d": metrics.same_identity_candidate_recall_d,
        },
        "rows": rows,
    }


def main() -> None:
    run_dir = Path("data/live_runs/targeted-run-1")
    if not run_dir.exists():
        # allow argument
        run_dir = Path(sys.argv[1])
    incidents = [i for i in load_benchmark() if i["incident_id"] in TARGETED_INCIDENTS]
    cached = load_cached(run_dir)

    live = replay(incidents, cached, "live")
    mock = replay(incidents, cached, "mock")

    print("=" * 78)
    print("MOCK (deterministic) vs LIVE (Qwen3-30B via Featherless) — targeted subset, v3")
    print("=" * 78)
    for key in ["evaluated", "same", "diff", "under", "true_links", "false_merges",
                "fnl", "blocked_conflict_recall", "human_review", "insufficient",
                "blocked", "wss", "unsafe_under", "retrieval_recall"]:
        print(f"  {key:<22} mock={mock['metrics'][key]}  live={live['metrics'][key]}")

    print("\n--- PAIR-LEVEL TABLE (live) ---")
    print(f"{'incident':<36} {'pair':<18} {'truth':<10} {'state':<24} {'score':>6}")
    for r in sorted(live["rows"], key=lambda x: (x["incident"], x["pair"])):
        print(f"{r['incident']:<36} {r['pair']:<18} {r['identity_truth']:<10} "
              f"{r['state']:<24} {r['score']:>6.3f}")

    # Earliest-divergence for same-identity pairs that did not link
    print("\n--- EARLIEST DIVERGENCE: same-identity pairs not linked (live) ---")
    expected = {i["incident_id"]: i["ground_truth"]["expected_pair"] for i in incidents
                if i["ground_truth"]["expected_pair"]}
    for r in sorted(live["rows"], key=lambda x: (x["incident"], x["pair"])):
        if r["identity_truth"] != "same_identity":
            continue
        if r["state"] == "link_recommended":
            continue
        iid = r["incident"]
        a, b = r["pair"].split("<->")
        rec_a, rec_b = None, None
        for inc in incidents:
            if inc["incident_id"] == iid:
                for rec in inc["records"]:
                    if rec["record_id"] == a:
                        rec_a = rec
                    if rec["record_id"] == b:
                        rec_b = rec
        exp = set(rec_a.get("text", "").split()) if rec_a else set()
        live_a = cached.get(a, {})
        live_b = cached.get(b, {})
        la = {f["key"] for f in live_a.get("fields", [])}
        lb = {f["key"] for f in live_b.get("fields", [])}
        ea = RECORD_EXPECTED_FIELDS.get(a, set())
        eb = RECORD_EXPECTED_FIELDS.get(b, set())
        omitted = (ea - la) | (eb - lb)
        print(f"  {iid}  {r['pair']}")
        print(f"    state={r['state']} score={r['score']} rules={r['rules']}")
        print(f"    conflicts={r['conflicts']} supporting={r['supporting']}")
        if omitted:
            print(f"    MISSING EXPECTED FIELDS: {sorted(omitted)}  <-- extraction omission")
        else:
            print(f"    all expected fields present -> divergence in scoring/decision policy")
        # classification
        if omitted and set(r["rules"]) == set():
            stage = "candidate_retrieval"
        elif omitted:
            stage = "extraction"
        elif r["state"] == "human_review_required":
            stage = "score_threshold"
        elif r["state"] == "insufficient_evidence":
            stage = "score_threshold"
        else:
            stage = "decision_policy"
        print(f"    EARLIEST FAILURE STAGE: {stage}")

    # Failure taxonomy
    print("\n--- FAILURE TAXONOMY (live, all pairs) ---")
    taxonomy = Counter()
    for r in live["rows"]:
        if r["identity_truth"] == "different_identity" and r["state"] == "link_recommended":
            taxonomy["false_merge"] += 1
        elif r["identity_truth"] == "same_identity":
            if r["state"] == "link_recommended":
                taxonomy["true_link"] += 1
            else:
                a, b = r["pair"].split("<->")
                ea = RECORD_EXPECTED_FIELDS.get(a, set())
                eb = RECORD_EXPECTED_FIELDS.get(b, set())
                la = {f["key"] for f in cached.get(a, {}).get("fields", [])}
                lb = {f["key"] for f in cached.get(b, {}).get("fields", [])}
                if (ea - la) or (eb - lb):
                    taxonomy["extraction_omission"] += 1
                elif r["state"] == "human_review_required":
                    taxonomy["score_threshold"] += 1
                else:
                    taxonomy["insufficient_evidence"] += 1
        elif r["identity_truth"] == "different_identity":
            taxonomy["correct_block"] += 1
        else:
            taxonomy["under_specified_handled"] += 1
    for k, v in sorted(taxonomy.items()):
        print(f"  {k:<28} {v}")


if __name__ == "__main__":
    main()
