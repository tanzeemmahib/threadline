"""Phase 10 validation: candidate-priority benchmark revalidation and 3-run
artifact reproducibility with canonical candidate artifacts."""
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")

_NODE_INVENTORY_KNOWN = 364  # expected total after Phase 10


def node_inventory() -> tuple[str, int]:
    test_path = Path("tests/test_identity_resolution.py")
    text = test_path.read_text(encoding="utf-8")
    nodes = []
    current_class = None
    for line in text.splitlines():
        m = re.match(r"^class (\w+)", line)
        if m:
            current_class = m.group(1)
            continue
        m = re.match(r"^    def (test_\w+)", line)
        if m and current_class:
            nodes.append(f"{current_class}::{m.group(1)}")
    blob = "\n".join(sorted(nodes))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest(), len(nodes)


def run_benchmark() -> dict:
    from app.services.identity_benchmark import (
        build_universe_table,
        calculate_metrics,
        load_benchmark,
        run_mode_mock_extraction,
    )

    incidents = load_benchmark()
    universe = build_universe_table(incidents)
    results = run_mode_mock_extraction(incidents)
    metrics = calculate_metrics(results, incidents, system="mock_extraction")
    cg = metrics.candidate_gen
    cm = cg.phase10_candidate_metrics
    out = {
        "incidents": metrics.total_incidents,
        "records": metrics.total_records,
        "possible_pairs": metrics.total_possible_pairs,
        "evaluated": metrics.evaluated_pairs,
        "universe_same": metrics.same_identity_candidate_recall_d,
        "universe_diff": metrics.blocking_conflict_candidate_recall_d,
        "universe_ambig": metrics.ambiguous_candidate_recall_d,
        "link_recommended": metrics.link_recommended_count,
        "human_review": metrics.human_review_required_count,
        "insufficient": metrics.insufficient_evidence_count,
        "blocked": metrics.blocked_by_conflict_count,
        "do_not_link": metrics.do_not_link_count,
        "true_links": metrics.true_link_count,
        "false_merges": metrics.false_merge_count,
        "false_non_matches": metrics.false_non_match_count,
        "wss": metrics.weighted_safety_score,
        "same_id_candidate_recall_n": metrics.same_identity_candidate_recall_n,
        "same_id_candidate_recall_d": metrics.same_identity_candidate_recall_d,
        "retrieval": cm["retrieval"],
        "cap": cm["cap"],
        "emission": cm["emission"],
        "expansion": cm["expansion"],
        "ranks_max_final": cm["ranks"]["max_final"],
        "ranks_median_final": cm["ranks"]["median_final"],
        "added_gt": cm["added_pair_ground_truth"],
        "strong_v2": cg.strong_identifier_survival_v2,
        "strong_v2_eligible": cg.strong_identifier_survival_v2_eligible,
        "strong_v2_removed": cg.strong_identifier_survival_v2_removed_by_cap,
        "unique_v1": cg.unique_id_survival_v1,
        "unique_v1_eligible": cg.unique_id_survival_v1_eligible,
        "total_expansion_pairs": cg.total_expansion_pairs,
        "blocking_rule_hits": dict(cg.blocking_rule_hits),
        "metrics_version": cm["metrics_version"],
    }
    return out


def artifact_hash(tmp_dir: str) -> str:
    from app.services.identity_benchmark import (
        build_universe_table,
        calculate_metrics,
        generate_artifacts,
        load_benchmark,
        run_mode_mock_extraction,
    )

    incidents = load_benchmark()
    universe = build_universe_table(incidents)
    results = run_mode_mock_extraction(incidents)
    metrics = calculate_metrics(results, incidents, system="mock_extraction")
    legacy = calculate_metrics(results, incidents, system="legacy")
    generate_artifacts(results, incidents, universe, metrics, legacy, [], tmp_dir)
    artifact_path = Path(tmp_dir) / "candidate-artifact.json"
    blob = artifact_path.read_text(encoding="utf-8")
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def main() -> None:
    h, n = node_inventory()
    print(f"identity_resolution nodes={n} inventory_sha256={h}")

    print("\n=== PHASE 10 BENCHMARK REVALIDATION (mock_extraction) ===")
    run = run_benchmark()
    for k, v in run.items():
        print(f"  {k}: {v}")

    checks = {
        "false_merges == 0": run["false_merges"] == 0,
        "WSS >= 5": run["wss"] >= 5,
        "retrieval 14/16": (
            run["same_id_candidate_recall_n"] == 14
            and run["same_id_candidate_recall_d"] == 16
        ),
        "strong v2 removed by cap == 0": run["strong_v2_removed"] == 0,
        "strong v2 4/4": run["strong_v2"] == 4 and run["strong_v2_eligible"] == 4,
        "expansion zero on benchmark": run["total_expansion_pairs"] == 0,
        "metrics version 1.0": run["metrics_version"] == "1.0",
    }
    print("\n=== PHASE 10 INVARIANT CHECKS ===")
    for name, ok in checks.items():
        print(f"  {'OK ' if ok else 'FAIL'} {name}")

    print("\n=== 3-RUN REPRODUCIBILITY (candidate-artifact.json hashes) ===")
    hashes = []
    for i in range(3):
        with tempfile.TemporaryDirectory() as td:
            hashes.append(artifact_hash(td))
            print(f"  run {i + 1}: {hashes[i]}")
    print(f"  identical: {len(set(hashes)) == 1}")

    ok_all = all(checks.values()) and len(set(hashes)) == 1
    print(f"\n=== OVERALL: {'PASS' if ok_all else 'FAIL'} ===")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
