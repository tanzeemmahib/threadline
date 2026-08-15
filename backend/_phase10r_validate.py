"""Phase 10R validation: ground-truth integrity audit + dual-schema metrics
(v1 historical / v2 audited) + 3-run artifact reproducibility per schema."""
import hashlib
import json
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, ".")


def fixture_sha256() -> str:
    p = Path("fixtures/identity_benchmark.json")
    return hashlib.sha256(p.read_bytes()).hexdigest()


def node_inventory() -> tuple[str, int]:
    test_path = Path("tests/test_identity_resolution.py")
    text = test_path.read_text(encoding="utf-8")
    nodes, current = [], None
    for line in text.splitlines():
        m = re.match(r"^class (\w+)", line)
        if m:
            current = m.group(1)
            continue
        m = re.match(r"^    def (test_\w+)", line)
        if m and current:
            nodes.append(f"{current}::{m.group(1)}")
    blob = "\n".join(sorted(nodes))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest(), len(nodes)


def run_schema(schema: str) -> dict:
    from app.services.identity_benchmark import (
        build_universe_table,
        calculate_metrics,
        load_benchmark,
        run_mode_mock_extraction,
    )
    incidents = load_benchmark()
    universe = build_universe_table(incidents, ground_truth_schema=schema)
    results = run_mode_mock_extraction(incidents)
    m = calculate_metrics(results, incidents, system="mock_extraction",
                          ground_truth_schema=schema)
    return {
        "schema": schema,
        "universe": dict(Counter(u.identity_truth for u in universe)),
        "same_retrieval": f"{m.same_identity_candidate_recall_n}/"
                          f"{m.same_identity_candidate_recall_d}",
        "fnl": m.false_non_match_count,
        "true_links": m.true_link_count,
        "false_merges": m.false_merge_count,
        "human_review": m.human_review_required_count,
        "blocked": m.blocked_by_conflict_count,
        "insufficient": m.insufficient_evidence_count,
        "wss": m.weighted_safety_score,
        "strong_v2": f"{m.candidate_gen.strong_identifier_survival_v2}/"
                     f"{m.candidate_gen.strong_identifier_survival_v2_eligible}",
        "strong_removed": m.candidate_gen.strong_identifier_survival_v2_removed_by_cap,
        "retrieval_fn": m.candidate_gen.phase10_candidate_metrics["retrieval"][
            "positive_retrieval_fn"],
    }


def artifact_hash(schema: str, tmp_dir: str) -> str:
    from app.services.identity_benchmark import (
        build_universe_table,
        calculate_metrics,
        generate_artifacts,
        load_benchmark,
        run_mode_mock_extraction,
    )
    incidents = load_benchmark()
    universe = build_universe_table(incidents, ground_truth_schema=schema)
    results = run_mode_mock_extraction(incidents)
    metrics = calculate_metrics(results, incidents, system="mock_extraction",
                                ground_truth_schema=schema)
    legacy = calculate_metrics(results, incidents, system="legacy")
    generate_artifacts(results, incidents, universe, metrics, legacy, [], tmp_dir,
                       ground_truth_schema=schema)
    blob = (Path(tmp_dir) / "candidate-artifact.json").read_text(encoding="utf-8")
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def main() -> int:
    h, n = node_inventory()
    print(f"identity_resolution nodes={n} inventory_sha256={h}")
    print(f"fixture_sha256={fixture_sha256()}")

    print("\n=== GROUND-TRUTH AUDIT (historical v1 truth) ===")
    from app.services.identity_benchmark import audit_ground_truth, load_benchmark
    rows = audit_ground_truth(load_benchmark())
    print("audit ->", dict(Counter(r["audit"] for r in rows)))
    flagged = sorted(
        (r["incident_id"], r["record_a"], r["record_b"])
        for r in rows if r["audit"] == "label_conflicts_with_fixture_evidence"
    )
    print("unsupported pairs:", flagged)

    print("\n=== METRICS PER GROUND-TRUTH SCHEMA ===")
    results = {}
    for schema in ("v1", "v2"):
        results[schema] = run_schema(schema)
        print(f"  {schema}: {results[schema]}")

    print("\n=== 3-RUN REPRODUCIBILITY PER SCHEMA ===")
    ok = True
    for schema in ("v1", "v2"):
        hashes = []
        for _ in range(3):
            with tempfile.TemporaryDirectory() as td:
                hashes.append(artifact_hash(schema, td))
        same = len(set(hashes)) == 1
        ok = ok and same
        print(f"  {schema}: {hashes[0]} identical={same}")

    checks = {
        "v1 historical unchanged (16 same, FNL 10, WSS +5)": (
            results["v1"]["universe"]["same_identity"] == 16
            and results["v1"]["fnl"] == 10 and results["v1"]["wss"] == 5
        ),
        "v2 audited (14 same, FNL 8, WSS +25)": (
            results["v2"]["universe"]["same_identity"] == 14
            and results["v2"]["fnl"] == 8 and results["v2"]["wss"] == 25
        ),
        "zero false merges both schemas": (
            results["v1"]["false_merges"] == 0 and results["v2"]["false_merges"] == 0
        ),
        "strong v2 4/4, removed 0 both schemas": (
            results["v1"]["strong_v2"] == "4/4" and results["v2"]["strong_v2"] == "4/4"
            and results["v1"]["strong_removed"] == 0
            and results["v2"]["strong_removed"] == 0
        ),
        "exactly 5 unsupported pairs flagged": len(flagged) == 5,
        "reproducibility ok": ok,
    }
    print("\n=== PHASE 10R CHECKS ===")
    for name, ok_flag in checks.items():
        print(f"  {'OK ' if ok_flag else 'FAIL'} {name}")
    all_ok = all(checks.values())
    print(f"\n=== OVERALL: {'PASS' if all_ok else 'FAIL'} ===")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
