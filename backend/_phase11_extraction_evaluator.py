"""
Phase 11B — Extraction-Quality Evaluator

Computes per-field detection metrics, value-fidelity classification,
and unknown-key tracking for any extraction system (mock, live, etc.)
against the canonical RECORD_EXPECTED_FIELDS.

Usage:
    python _phase11_extraction_evaluator.py [--system mock_extraction|live_featherless] [--json PATH]
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, ".")

from app.services.identity_benchmark import (
    RECORD_EXPECTED_FIELDS,
    STRONG_IDENTIFIER_FIELDS,
    ExtractionMetrics,
    build_normalized_record,
    load_benchmark,
    mock_extract_fields,
    run_mode_mock_extraction,
)
from app.services.field_key_normalizer import normalize_field_key


# ── All canonical identity fields tracked by the evaluator ──
CANONICAL_FIELDS = [
    "name", "aliases", "age", "date_of_birth", "government_id",
    "phone", "email", "last_known_location", "shelter",
    "distinguishing_marks", "family_member_names", "timeline_event",
]

# ── Value fidelity classification ──
FIDELITY_CLASSES = [
    "exact_match",             # byte-identical or value-identical
    "normalization_equivalent", # e.g. phone with different formatting
    "partial_usable",           # e.g. birth year without full DOB
    "incorrect",                # wrong value extracted
    "hallucinated",             # not present in source text at all
    "omitted",                  # should have been extracted but wasn't
]


def classify_value_fidelity(
    field_key: str,
    extracted_value: Any,
    expected_raw_value: Any,
    source_text: str,
) -> str:
    """Classify the fidelity of an extracted value against expectations.

    This is a heuristic classifier. For production use, field-specific
    comparators should be used.
    """
    if extracted_value is None or extracted_value == "":
        return "omitted"

    ev = str(extracted_value).strip().lower()
    rv = str(expected_raw_value).strip().lower() if expected_raw_value else ""

    if not rv:
        # No expected raw value to compare against — check if hallucinated
        # by searching source text for the extracted value
        if ev and ev not in source_text.lower():
            return "hallucinated"
        return "exact_match"  # present in source, assume correct

    if ev == rv:
        return "exact_match"

    # Phone: check digit-only normalization
    if field_key == "phone":
        digits_ev = "".join(c for c in ev if c.isdigit())
        digits_rv = "".join(c for c in rv if c.isdigit())
        if digits_ev == digits_rv and len(digits_ev) >= 7:
            return "normalization_equivalent"

    # DOB: year-only vs full date
    if field_key == "date_of_birth":
        if ev in rv or rv in ev:
            return "partial_usable"

    # Name: case-insensitive match
    if field_key in ("name", "aliases"):
        if ev == rv:
            return "exact_match"

    # Check if value appears anywhere in source text
    if ev in source_text.lower():
        return "exact_match"

    return "incorrect"


def compute_extraction_quality(
    records_extractions: dict[str, dict],
    benchmark: list[dict],
) -> dict:
    """Compute per-field extraction quality metrics.

    Args:
        records_extractions: {record_id: {"fields": [...], "unknown_keys": [...], ...}}
        benchmark: loaded benchmark incidents list

    Returns:
        dict with per_field metrics, strong_id aggregate, unknown_keys summary,
        value_fidelity counts, and record-level details.
    """
    # Index of all records across all incidents
    all_records: dict[str, dict] = {}
    for inc in benchmark:
        for rec in inc["records"]:
            all_records[rec["record_id"]] = rec

    field_names = CANONICAL_FIELDS

    # ── Field detection (TP/FP/FN/TN) ──
    per_field: dict[str, dict] = {}
    unknown_key_counts: dict[str, int] = defaultdict(int)
    fidelity_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    record_details: dict[str, dict] = {}

    for fname in field_names:
        tp = fp = fn = tn = 0
        expected_count = 0
        for rid, rec_data in all_records.items():
            expected = RECORD_EXPECTED_FIELDS.get(rid, set())
            ext = records_extractions.get(rid, {})
            extracted_fields = ext.get("fields", [])
            extracted_keys = {f["key"] for f in extracted_fields if isinstance(f, dict)}

            should_extract = fname in expected
            if should_extract:
                expected_count += 1
            was_extracted = fname in extracted_keys

            if should_extract and was_extracted:
                tp += 1
            elif should_extract and not was_extracted:
                fn += 1
            elif not should_extract and was_extracted:
                fp += 1
            else:
                tn += 1

            # Value fidelity for this record/field
            if should_extract and was_extracted:
                # Find the extracted field value
                ev = next(
                    (f.get("value") for f in extracted_fields
                     if isinstance(f, dict) and f.get("key") == fname),
                    None,
                )
                fidelity = classify_value_fidelity(
                    fname, ev, None, rec_data.get("text", ""),
                )
            elif should_extract and not was_extracted:
                fidelity = "omitted"
            elif not should_extract and was_extracted:
                fidelity = "hallucinated"  # FP = hallucinated
            else:
                fidelity = "none"  # TN = correctly absent

            if fidelity != "none":
                fidelity_counts[fname][fidelity] += 1

        per_field[fname] = {
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": tp / (tp + fp) if (tp + fp) > 0 else 0.0,
            "recall": tp / (tp + fn) if (tp + fn) > 0 else 0.0,
            "f1": 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) > 0 else 0.0,
            "jaccard": tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0.0,
            "accuracy": (tp + tn) / (tp + fp + fn + tn) if (tp + fp + fn + tn) > 0 else 0.0,
            "present_field_accuracy": tp / expected_count if expected_count > 0 else 0.0,
            "expected_count": expected_count,
        }

    # ── Unknown keys ──
    for rid, ext in records_extractions.items():
        for uk in ext.get("unknown_keys", []):
            unknown_key_counts[uk] += 1

    # ── Per-record details ──
    for rid, rec_data in all_records.items():
        expected = RECORD_EXPECTED_FIELDS.get(rid, set())
        ext = records_extractions.get(rid, {})
        extracted_fields = ext.get("fields", [])
        extracted_keys = {f["key"] for f in extracted_fields if isinstance(f, dict)}

        missing = expected - extracted_keys
        extra = extracted_keys - expected
        correct = expected & extracted_keys

        record_details[rid] = {
            "expected": sorted(expected),
            "extracted": sorted(extracted_keys),
            "correct": sorted(correct),
            "missing": sorted(missing),
            "extra": sorted(extra),
            "unknown_keys": ext.get("unknown_keys", []),
            "status": ext.get("status", "unknown"),
            "latency_ms": ext.get("latency_ms"),
            "attempts": ext.get("attempts"),
            "error_class": ext.get("error_class"),
        }

    # ── Strong-ID aggregate ──
    sid_tp = sum(per_field[f]["tp"] for f in STRONG_IDENTIFIER_FIELDS if f in per_field)
    sid_fp = sum(per_field[f]["fp"] for f in STRONG_IDENTIFIER_FIELDS if f in per_field)
    sid_fn = sum(per_field[f]["fn"] for f in STRONG_IDENTIFIER_FIELDS if f in per_field)
    sid_precision = sid_tp / (sid_tp + sid_fp) if (sid_tp + sid_fp) > 0 else 0.0
    sid_recall = sid_tp / (sid_tp + sid_fn) if (sid_tp + sid_fn) > 0 else 0.0

    # ── Overall extraction success ──
    total_records = len(all_records)
    ok_records = sum(1 for rid in all_records if records_extractions.get(rid, {}).get("status") == "ok")

    return {
        "system": "extraction_evaluator",
        "total_records": total_records,
        "extraction_success": f"{ok_records}/{total_records}",
        "extraction_success_rate": ok_records / total_records if total_records > 0 else 0.0,
        "per_field": per_field,
        "strong_identifier": {
            "tp": sid_tp, "fp": sid_fp, "fn": sid_fn,
            "precision": sid_precision,
            "recall": sid_recall,
        },
        "unknown_keys": dict(unknown_key_counts),
        "fidelity_summary": {
            field: dict(counts) for field, counts in fidelity_counts.items()
        },
        "record_details": record_details,
    }


def evaluate_mock_extraction(benchmark: list[dict]) -> dict:
    """Evaluate extraction quality using deterministic mock extraction."""
    records_extractions: dict[str, dict] = {}
    for inc in benchmark:
        for rec in inc["records"]:
            rid = rec["record_id"]
            fields = mock_extract_fields(
                rec.get("text", ""), rid, rec.get("language", "English"),
            )
            # Canonicalize keys through the shared normalization path
            canonical_fields = []
            unknown_keys = []
            for f in fields:
                nk = normalize_field_key(f.key)
                if nk.canonical_key:
                    canonical_fields.append({
                        "key": nk.canonical_key,
                        "value": f.value,
                        "certainty": getattr(f, "certainty", None),
                        "raw_key": f.key,
                    })
                else:
                    unknown_keys.append(f.key)
                    # Still preserve the field for analysis
                    canonical_fields.append({
                        "key": f.key,
                        "value": f.value,
                        "certainty": getattr(f, "certainty", None),
                        "raw_key": f.key,
                    })

            records_extractions[rid] = {
                "status": "ok",
                "latency_ms": 0,
                "attempts": 1,
                "fields": canonical_fields,
                "unknown_keys": unknown_keys,
                "error_class": None,
            }

    return compute_extraction_quality(records_extractions, benchmark)


def print_report(result: dict) -> None:
    """Pretty-print the extraction quality report."""
    print("=" * 72)
    print("EXTRACTION-QUALITY EVALUATOR — Phase 11B")
    print("=" * 72)
    print(f"total records: {result['total_records']}")
    print(f"extraction success: {result['extraction_success']} ({result['extraction_success_rate']:.1%})")
    print()

    # ── Per-field table ──
    print(f"{'Field':<24} {'TP':>4} {'FP':>4} {'FN':>4} {'TN':>4} {'Prec':>7} {'Recall':>7} {'F1':>7} {'Jacc':>7} {'Present':>8}")
    print("-" * 88)
    for fname in CANONICAL_FIELDS:
        if fname not in result["per_field"]:
            continue
        m = result["per_field"][fname]
        if m["expected_count"] == 0 and m["tp"] == 0 and m["fp"] == 0:
            continue  # skip fields not relevant to any record
        print(
            f"{fname:<24} {m['tp']:>4} {m['fp']:>4} {m['fn']:>4} {m['tn']:>4} "
            f"{m['precision']:>7.1%} {m['recall']:>7.1%} {m['f1']:>7.1%} "
            f"{m['jaccard']:>7.1%} {m['present_field_accuracy']:>8.1%}"
        )
    print()

    # ── Strong-ID aggregate ──
    sid = result["strong_identifier"]
    print(f"Strong-ID aggregate: TP={sid['tp']} FP={sid['fp']} FN={sid['fn']} "
          f"Precision={sid['precision']:.1%} Recall={sid['recall']:.1%}")
    print()

    # ── Unknown keys ──
    uk = result["unknown_keys"]
    if uk:
        print("Unknown keys:")
        for key, count in sorted(uk.items(), key=lambda x: -x[1]):
            print(f"  {key}: {count}")
    else:
        print("Unknown keys: (none)")
    print()

    # ── Value fidelity summary ──
    print("Value fidelity by field:")
    print(f"  {'Field':<24} {'exact':>6} {'norm-equiv':>10} {'partial':>7} {'incorrect':>9} {'hallucinated':>12} {'omitted':>7}")
    print("  " + "-" * 80)
    for fname in CANONICAL_FIELDS:
        counts = result["fidelity_summary"].get(fname, {})
        if not counts:
            continue
        print(
            f"  {fname:<24} "
            f"{counts.get('exact_match', 0):>6} "
            f"{counts.get('normalization_equivalent', 0):>10} "
            f"{counts.get('partial_usable', 0):>7} "
            f"{counts.get('incorrect', 0):>9} "
            f"{counts.get('hallucinated', 0):>12} "
            f"{counts.get('omitted', 0):>7}"
        )
    print()

    # ── Per-record summary ──
    print("Per-record summary:")
    print(f"  {'Record':<16} {'Status':<8} {'Correct':>8} {'Missing':>8} {'Extra':>6} {'Lat(ms)':>8}")
    print("  " + "-" * 60)
    for rid, det in sorted(result["record_details"].items()):
        print(
            f"  {rid:<16} {det['status']:<8} "
            f"{len(det['correct']):>8} {len(det['missing']):>8} "
            f"{len(det['extra']):>6} "
            f"{det.get('latency_ms', 0) or 0:>8.0f}"
        )


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", choices=["mock_extraction"], default="mock_extraction")
    parser.add_argument("--json", type=str, help="Save report to JSON file")
    args = parser.parse_args()

    benchmark = load_benchmark()

    if args.system == "mock_extraction":
        result = evaluate_mock_extraction(benchmark)
    else:
        print(f"Unknown system: {args.system}", file=sys.stderr)
        return 1

    print_report(result)

    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        print(f"\nReport saved to: {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
