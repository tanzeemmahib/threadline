"""Phase 9R validation: collect node inventory hash and benchmark metrics."""
import hashlib
import json
import sys

sys.path.insert(0, ".")


def node_inventory() -> str:
    import re
    from pathlib import Path

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


def main() -> None:
    h, n = node_inventory()
    print(f"identity_resolution nodes={n} inventory_sha256={h}")

    from app.services.identity_benchmark import (
        load_benchmark,
        run_mode_mock_extraction,
        calculate_metrics,
        build_universe_table,
    )

    incidents = load_benchmark()
    universe = build_universe_table(incidents)
    results = run_mode_mock_extraction(incidents)
    metrics = calculate_metrics(results, incidents, system="mock_extraction")

    print("\n=== BENCHMARK REVALIDATION (after Phase 9R) ===")
    print(f"incidents={metrics.total_incidents} records={metrics.total_records} "
          f"possible_pairs={metrics.total_possible_pairs} evaluated={metrics.evaluated_pairs}")
    print(f"universe: same={metrics.same_identity_candidate_recall_d} "
          f"diff={metrics.blocking_conflict_candidate_recall_d} "
          f"ambig={metrics.ambiguous_candidate_recall_d}")
    print(f"link_rec={metrics.link_recommended_count} human_rev={metrics.human_review_required_count} "
          f"insuff={metrics.insufficient_evidence_count} blocked={metrics.blocked_by_conflict_count} "
          f"do_not={metrics.do_not_link_count}")
    print(f"true_links={metrics.true_link_count} false_merges={metrics.false_merge_count} "
          f"false_non_matches={metrics.false_non_match_count} WSS={metrics.weighted_safety_score}")
    print(f"same_id_candidate_recall={metrics.same_identity_candidate_recall_n}/"
          f"{metrics.same_identity_candidate_recall_d}")
    print(f"expected_candidate_recall={metrics.expected_candidate_recall_n}/"
          f"{metrics.expected_candidate_recall_d}")
    print(f"blocking_conflict_recall={metrics.blocking_conflict_candidate_recall_n}/"
          f"{metrics.blocking_conflict_candidate_recall_d}")
    print(f"ambiguous_recall={metrics.ambiguous_candidate_recall_n}/"
          f"{metrics.ambiguous_candidate_recall_d}")
    print(f"blocking_rule_hits={dict(metrics.candidate_gen.blocking_rule_hits)}")
    cg = metrics.candidate_gen
    print(f"unique_id_survival_v1 (legacy)={cg.unique_id_survival_v1} "
          f"eligible={cg.unique_id_survival_v1_eligible} removed={cg.unique_id_survival_v1_removed_by_cap}")
    print(f"strong_identifier_survival_v2={cg.strong_identifier_survival_v2} "
          f"eligible={cg.strong_identifier_survival_v2_eligible} removed={cg.strong_identifier_survival_v2_removed_by_cap}")
    print(f"blocking_tp={metrics.candidate_gen.blocking_tp} "
          f"blocking_fp={metrics.candidate_gen.blocking_fp} "
          f"blocking_fn={metrics.candidate_gen.blocking_fn} "
          f"blocking_recall={metrics.candidate_gen.blocking_recall:.4f}")

    # Phone-fixture traces
    print("\n=== PHONE FIXTURE TRACES ===")
    from app.services.phone_parser import parse_phone, parse_phone_with_ocr, PhonePrefix
    phone_fixtures = {
        "PHONEFMT-A1": "Karim Mansour, phone (555) 123-4567.",
        "PHONEFMT-A2": "Karim Mansour, phone +1-555-123-4567.",
        "OCR-A1": "Nadia Saleh, DOB 20l2-03-10 (OCR noise), phone +l-555-3434.",
        "OCR-A2": "Nadia Saleh, DOB 2012-03-10, phone +1-555-3434.",
        "MULTI-A1": "Amal Rafiq, DOB 2005-06-12, phone +1-555-9876",
        "MULTI-A2": "Amal Rafiq, age 21, phone 5559876",
        "DOBCONF-A1": "Lina Haddad, DOB 2005-06-12, phone +1-555-4321.",
        "DOBCONF-A2": "Lina Haddad, DOB 2002-03-28, phone +1-555-4321.",
    }
    for rid, raw in phone_fixtures.items():
        p = parse_phone_with_ocr(raw.split("phone ")[1] if "phone " in raw else raw)
        print(f"{rid}: raw={p.raw_value!r} intl={p.explicit_international} "
              f"prefix={p.explicit_prefix.value} cc={p.country_code or '-'} "
              f"nat={p.national_number or '-'} ocr={bool(p.ocr_repairs)}")


if __name__ == "__main__":
    main()
