"""Recompute Phase 11 V2 full benchmark metrics from existing raw-outputs.json."""
import json, sys, time, hashlib
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.identity_benchmark import (
    load_benchmark, build_universe_table,
    _make_incident_result, _add_structured_pairs, calculate_metrics,
    identity_assignment_sha256, load_identity_assignments,
    RECORD_EXPECTED_FIELDS,
)
from app.schemas.models import NormalizedRecord, ExtractedField, Certainty
from app.services.field_key_normalizer import normalize_field_key

ALL_CANONICAL_KEYS = sorted(RECORD_EXPECTED_FIELDS["GOV-A1"]
    | RECORD_EXPECTED_FIELDS["MULTI-A1"]
    | RECORD_EXPECTED_FIELDS["SIB-A1"]
    | RECORD_EXPECTED_FIELDS["TRANS-A1"]
    | RECORD_EXPECTED_FIELDS["DUP-A1"]
    | {"email", "language", "aliases", "family_member_names", "shelter", "timeline_event"})

RUN_DIR = Path("data/live_runs_phase11/full-prompt-v2-run-1")


def build_record(rec: dict, extraction: dict) -> NormalizedRecord:
    fields = []
    for f in extraction.get("fields", []):
        try:
            certainty = Certainty(f["certainty"])
        except (ValueError, KeyError):
            certainty = Certainty.estimated
        fields.append(ExtractedField(
            field_id=f'{rec["record_id"]}-{f["key"]}',
            key=f["key"], label=f["key"],
            value=f["value"], certainty=certainty,
            source_span_id=f'{rec["record_id"]}-{f["key"]}-live',
        ))
    return NormalizedRecord(
        record_id=rec["record_id"],
        source_type=rec.get("source_type", "unknown"),
        language=rec.get("language", "English"),
        text=rec.get("text", ""),
        display_name=rec.get("display_name", rec["record_id"]),
        safe_text=rec.get("safe_text", rec.get("text", "")),
        fields=fields,
    )


def compute_extraction_quality(extraction_map: dict, incidents: list) -> dict:
    per_field = {k: {"tp": 0, "fp": 0, "fn": 0, "expected": 0, "extracted": 0}
                 for k in ALL_CANONICAL_KEYS}
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
                in_exp = key in expected
                in_ext = key in extracted_keys
                if in_exp:
                    per_field[key]["expected"] += 1
                if in_ext:
                    per_field[key]["extracted"] += 1
                if in_exp and in_ext:
                    per_field[key]["tp"] += 1; total_tp += 1
                elif in_exp and not in_ext:
                    per_field[key]["fn"] += 1; total_fn += 1
                elif not in_exp and in_ext:
                    per_field[key]["fp"] += 1; total_fp += 1; hallucinated += 1

    field_results = {}
    for key, c in per_field.items():
        tp, fp, fn = c["tp"], c["fp"], c["fn"]
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        if c["expected"] > 0 or c["extracted"] > 0:
            field_results[key] = {"expected": c["expected"], "extracted": c["extracted"],
                                   "tp": tp, "fp": fp, "fn": fn,
                                   "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4)}

    mp = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    mr = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    mf1 = 2 * mp * mr / (mp + mr) if (mp + mr) > 0 else 0.0

    return {
        "total_tp": total_tp, "total_fp": total_fp, "total_fn": total_fn,
        "hallucinated_fields": hallucinated, "unknown_key_count": unknown_total,
        "micro_precision": round(mp, 4), "micro_recall": round(mr, 4), "micro_f1": round(mf1, 4),
        "records_ok": sum(1 for e in extraction_map.values() if e["status"] == "ok"),
        "records_total": len(extraction_map), "per_field": field_results,
    }


def main():
    # Load raw outputs
    raw_path = RUN_DIR / "raw-outputs.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    extraction_map = raw.get("records", {})

    # Load benchmark
    incidents = load_benchmark()
    assignments = load_identity_assignments()
    subset_assignments = {rid: fid for rid, fid in assignments.items()
                          if rid in extraction_map}

    print(f"records in extraction_map: {len(extraction_map)}")
    ok = sum(1 for e in extraction_map.values() if e["status"] == "ok")
    err = sum(1 for e in extraction_map.values() if e["status"] == "error")
    print(f"ok: {ok}, errors: {err}")

    if err:
        for rid, e in extraction_map.items():
            if e["status"] == "error":
                print(f"  ERROR {rid}: {e.get('error_class','?')} {e.get('error_preview','')[:120]}")

    # Run matching pipeline
    incident_results = []
    for inc in incidents:
        ir = _make_incident_result(inc)
        recs = [build_record(r, extraction_map[r["record_id"]]) for r in inc["records"]]
        _add_structured_pairs(ir, recs, inc, "live_featherless")
        incident_results.append(ir)

    metrics = calculate_metrics(
        incident_results, incidents,
        system="live_featherless", ground_truth_schema="v3",
        identity_assignments=subset_assignments,
    )

    # Build universe and pair rows
    universe = build_universe_table(
        incidents, ground_truth_schema="v3", identity_assignments=subset_assignments)
    pair_truth = {(u.incident_id, frozenset({u.record_a, u.record_b})): u for u in universe}

    pair_rows = []
    linked_pairs = []
    for ir in incident_results:
        for pr in ir.pair_results:
            key = (ir.incident_id, frozenset({pr.record_id_a, pr.record_id_b}))
            u = pair_truth.get(key)
            row = {
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
            }
            pair_rows.append(row)
            if pr.linkage_state == "link_recommended":
                linked_pairs.append(row)

    # Extraction quality
    extraction_quality = compute_extraction_quality(extraction_map, incidents)

    # Print results
    print()
    print("=" * 72)
    print("FULL PROMPT V2 BENCHMARK — RECOMPUTED")
    print("=" * 72)
    print(f"extraction: {extraction_quality['records_ok']}/{extraction_quality['records_total']} ok")
    print(f"extraction quality: recall={extraction_quality['micro_recall']:.4f} "
          f"precision={extraction_quality['micro_precision']:.4f} "
          f"f1={extraction_quality['micro_f1']:.4f}")
    print(f"hallucinated fields: {extraction_quality['hallucinated_fields']}")
    print(f"unknown keys: {extraction_quality['unknown_key_count']}")
    print()
    print(f"evaluated_pairs: {metrics.evaluated_pairs}")
    print(f"same_identity_pairs: {metrics.same_identity_pairs}")
    print(f"different_identity_pairs: {metrics.different_identity_pairs}")
    print(f"decision_state_counts: {metrics.decision_state_counts}")
    print(f"true_link_count: {metrics.true_link_count}")
    print(f"false_merge_count: {metrics.false_merge_count}")
    print(f"false_non_match_count: {metrics.false_non_match_count}")
    print(f"blocked_conflict_recall: {metrics.blocked_conflict_recall}")
    print(f"human_review_required_count: {metrics.human_review_required_count}")
    print(f"insufficient_evidence_count: {metrics.insufficient_evidence_count}")
    print(f"blocked_by_conflict_count: {metrics.blocked_by_conflict_count}")
    print(f"unsafe_under_specified_link_count: {metrics.unsafe_under_specified_link_count}")
    print(f"WSS: {metrics.weighted_safety_score}")
    print()

    # Retrieval metrics
    print(f"retrieval recall: {metrics.same_identity_candidate_recall}")
    print(f"retrieval n/d: {metrics.same_identity_candidate_recall_n}/{metrics.same_identity_candidate_recall_d}")

    print(f"\n--- LINKED PAIRS ({len(linked_pairs)}) ---")
    for lp in sorted(linked_pairs, key=lambda r: r["total_score"], reverse=True):
        print(f"  {lp['incident']:<36} {lp['pair']:<18} "
              f"truth={lp['identity_truth']:<12} score={lp['total_score']:.4f}")

    # Save updated artifact
    artifact = {
        "execution_mode": "live_provider",
        "benchmark_version": "IDENTITY-BENCH-v1",
        "fixture_sha256": hashlib.sha256(
            (Path(__file__).resolve().parent / "fixtures" / "identity_benchmark.json").read_bytes()
        ).hexdigest(),
        "ground_truth_schema": "v3",
        "identity_assignment_sha256": identity_assignment_sha256(assignments),
        "provider": "openai_compatible",
        "model": raw.get("model", ""),
        "temperature": 0.0,
        "prompt_version": "v2",
        "run_id": "full-prompt-v2-run-1",
        "timestamp": time.time(),
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
            "n": metrics.same_identity_candidate_recall_n,
            "d": metrics.same_identity_candidate_recall_d,
            "recall": metrics.same_identity_candidate_recall,
        },
        "safety": {
            "different_identity_auto_links": metrics.false_merge_count,
            "under_specified_auto_links": metrics.unsafe_under_specified_link_count,
            "blocked_conflict_recall": metrics.blocked_conflict_recall,
        },
        "pair_rows": pair_rows,
    }
    art_path = RUN_DIR / "live-artifact.json"
    art_path.parent.mkdir(parents=True, exist_ok=True)
    art_path.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")
    print(f"\nartifact updated: {art_path}")


if __name__ == "__main__":
    main()
