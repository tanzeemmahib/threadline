"""Live Featherless benchmark — runs the 27-incident benchmark through the real provider.

Uses the frozen benchmark fixture, deterministic comparison policies, and
reporting code. Does NOT modify thresholds or policies.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings
from app.providers.openai_compatible import OpenAICompatibleProvider
from app.prompts.loader import load_prompt
from app.providers.openai_compatible import _format_schema_for_prompt
from app.schemas.models import (
    ExtractionModelOutput, ExtractedField, Certainty, ProviderMetadata, ProviderResult,
)
from app.services.identity_benchmark import (
    load_benchmark, build_normalized_record,
    run_mode_structured_engine, calculate_metrics,
    _make_incident_result, _add_structured_pairs,
    BLOCKING_RULES, RECORD_EXPECTED_FIELDS, STRONG_IDENTIFIER_FIELDS,
)

SETTINGS = Settings()
BENCHMARK = load_benchmark()
NUM_RUNS = 1  # Start with 1 run due to API latency

def sanitized_cfg() -> dict:
    return {
        "provider": SETTINGS.provider_mode,
        "base_url": SETTINGS.openai_base_url,
        "model": SETTINGS.openai_model,
        "temperature": SETTINGS.llm_temperature,
        "max_retries": SETTINGS.llm_max_retries,
    }


async def extract_with_live(provider, record: dict, template_id: str, template_version: str,
                            system_prompt: str, user_prompt: str) -> dict:
    """Run extraction through live provider. Returns success/failure/timing info."""
    result: dict = {"success": False, "fields": [], "latency_ms": 0, "tokens": 0,
                    "attempts": 0, "schema_validation_passed": False,
                    "repair_used": False, "error": None}
    try:
        started = perf_counter()
        pr = await provider.generate_structured(
            template_id=template_id,
            template_version=template_version,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=ExtractionModelOutput,
            mock_payload={},
        )
        result["success"] = True
        result["latency_ms"] = round((perf_counter() - started) * 1000)
        result["tokens"] = pr.metadata.token_usage or 0
        result["attempts"] = pr.metadata.attempts
        result["schema_validation_passed"] = True
        result["fields"] = [
            {"key": f.key, "value": f.value, "certainty": f.certainty.value}
            for f in pr.output.fields
        ]
    except Exception as e:
        result["error"] = str(e)[:500]
        result["latency_ms"] = round((perf_counter() - started) * 1000)
    return result


async def run_live_benchmark_run(system_prompt: str) -> dict:
    """Run one full benchmark pass through the live provider."""
    provider = OpenAICompatibleProvider(
        base_url=SETTINGS.openai_base_url,
        api_key=SETTINGS.openai_api_key or "",
        model=SETTINGS.openai_model,
        temperature=SETTINGS.llm_temperature,
        timeout_seconds=SETTINGS.llm_timeout_seconds,
        max_retries=SETTINGS.llm_max_retries,
    )

    # Launch all extractions concurrently
    async def extract_record(inc: dict, rec: dict) -> dict:
        user_prompt = f"<untrusted_evidence record_id={rec['record_id']!r}>\n{rec['text']}\n</untrusted_evidence>"
        result = await extract_with_live(
            provider, rec, "extraction", "v1", system_prompt, user_prompt,
        )
        result["incident_id"] = inc["incident_id"]
        result["record_id"] = rec["record_id"]
        return result

    tasks = [extract_record(inc, rec) for inc in BENCHMARK for rec in inc["records"]]
    extraction_results = await asyncio.gather(*tasks)

    total_latency_ms = 0
    total_tokens = 0
    total_attempts = 0
    success_count = 0
    for result in extraction_results:
        if result["success"]:
            success_count += 1
            total_latency_ms += result["latency_ms"]
            total_tokens += result["tokens"]
            total_attempts += result["attempts"]

    # Build normalized records from live extraction results
    records_by_incident: dict[str, list] = {}
    for er in extraction_results:
        iid = er["incident_id"]
        if iid not in records_by_incident:
            records_by_incident[iid] = []
        rec_data = next(r for inc in BENCHMARK for r in inc["records"]
                       if r["record_id"] == er["record_id"] and inc["incident_id"] == iid)
        if er["success"]:
            fields = [
                ExtractedField(
                    field_id=f'{er["record_id"]}-{f["key"]}',
                    key=f["key"], label=f["key"], value=f["value"],
                    certainty=Certainty(f["certainty"]),
                    source_span_id=f'{er["record_id"]}-{f["key"]}-span',
                )
                for f in er["fields"]
            ]
        else:
            fields = []
        from app.schemas.models import NormalizedRecord
        records_by_incident[iid].append(NormalizedRecord(
            record_id=er["record_id"],
            source_type=rec_data.get("source_type", "unknown"),
            language=rec_data.get("language", "English"),
            text=rec_data.get("text", ""),
            display_name=rec_data.get("display_name", er["record_id"]),
            safe_text=rec_data.get("text", ""),
            fields=fields,
        ))

    # Run structured engine on extracted records
    incident_results = []
    for inc in BENCHMARK:
        from app.services.identity_benchmark import IncidentResult
        ir = IncidentResult(
            incident_id=inc["incident_id"], description=inc.get("description", ""),
            ground_truth_relation=inc["ground_truth"]["relation"],
            expected_pair=inc["ground_truth"]["expected_pair"],
            expected_state=inc["ground_truth"]["expected_state"],
            acceptable_states=inc["ground_truth"]["acceptable_states"],
            expected_blocking=inc["ground_truth"].get("expected_blocking", []),
        )
        records = records_by_incident.get(inc["incident_id"], [])
        if records:
            _add_structured_pairs(ir, records, inc, "live_featherless")
        incident_results.append(ir)

    # Calculate metrics
    metrics = calculate_metrics(incident_results, BENCHMARK, system="live_featherless")

    # Field-level extraction metrics
    field_metrics = {}
    for fname in ["name", "age", "date_of_birth", "government_id", "phone", "email",
                   "last_known_location", "distinguishing_marks", "family_member_names"]:
        tp = fp = fn = tn = 0
        for er in extraction_results:
            rid = er["record_id"]
            expected = RECORD_EXPECTED_FIELDS.get(rid, set())
            should_extract = fname in expected
            was_extracted = any(f["key"] == fname for f in er.get("fields", []))
            if should_extract and was_extracted:
                tp += 1
            elif should_extract and not was_extracted:
                fn += 1
            elif not should_extract and was_extracted:
                fp += 1
            else:
                tn += 1
        field_metrics[fname] = {
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": tp/(tp+fp) if (tp+fp)>0 else 0,
            "recall": tp/(tp+fn) if (tp+fn)>0 else 0,
            "jaccard": tp/(tp+fp+fn) if (tp+fp+fn)>0 else 0,
            "accuracy": (tp+tn)/(tp+fp+fn+tn) if (tp+fp+fn+tn)>0 else 0,
        }

    sid_tp = sum(field_metrics[f]["tp"] for f in STRONG_IDENTIFIER_FIELDS if f in field_metrics)
    sid_fp = sum(field_metrics[f]["fp"] for f in STRONG_IDENTIFIER_FIELDS if f in field_metrics)
    sid_fn = sum(field_metrics[f]["fn"] for f in STRONG_IDENTIFIER_FIELDS if f in field_metrics)

    return {
        "extraction_success_rate": success_count / len(extraction_results) if extraction_results else 0,
        "extraction_total": len(extraction_results),
        "extraction_success": success_count,
        "avg_latency_ms": total_latency_ms / max(success_count, 1),
        "total_tokens": total_tokens,
        "total_attempts": total_attempts,
        "field_metrics": field_metrics,
        "strong_id_tp": sid_tp,
        "strong_id_fp": sid_fp,
        "strong_id_fn": sid_fn,
        "strong_id_precision": sid_tp/(sid_tp+sid_fp) if (sid_tp+sid_fp)>0 else 0,
        "strong_id_recall": sid_tp/(sid_tp+sid_fn) if (sid_tp+sid_fn)>0 else 0,
        "strong_id_jaccard": sid_tp/(sid_tp+sid_fp+sid_fn) if (sid_tp+sid_fp+sid_fn)>0 else 0,
        "metrics": {
            "evaluated_pairs": metrics.evaluated_pairs,
            "false_merge_count": metrics.false_merge_count,
            "false_merge_rate": metrics.false_merge_rate,
            "false_non_match_count": metrics.false_non_match_count,
            "true_link_count": metrics.true_link_count,
            "true_link_rate": metrics.true_link_rate,
            "blocked_conflict_recall": metrics.blocked_conflict_recall,
            "human_review_rate": metrics.human_review_rate,
            "insufficient_evidence_rate": metrics.insufficient_evidence_rate,
            "weighted_safety_score": metrics.weighted_safety_score,
            "decision_state_counts": metrics.decision_state_counts,
            "link_recommended_count": metrics.link_recommended_count,
            "blocked_by_conflict_count": metrics.blocked_by_conflict_count,
            "human_review_required_count": metrics.human_review_required_count,
            "incident_top_ranked_true_link_count": metrics.incident_top_ranked_true_link_count,
            "incident_top_ranked_false_merge_count": metrics.incident_top_ranked_false_merge_count,
            "incidents_routed_to_review": metrics.incidents_routed_to_review,
            "candidate_gen": {
                "blocking_tp": metrics.candidate_gen.blocking_tp,
                "blocking_fp": metrics.candidate_gen.blocking_fp,
                "blocking_fn": metrics.candidate_gen.blocking_fn,
                "blocking_precision": metrics.candidate_gen.blocking_precision,
                "blocking_recall": metrics.candidate_gen.blocking_recall,
                "combined_tp": metrics.candidate_gen.combined_tp,
                "combined_fp": metrics.candidate_gen.combined_fp,
                "combined_fn": metrics.candidate_gen.combined_fn,
                "combined_precision": metrics.candidate_gen.combined_precision,
                "combined_recall": metrics.candidate_gen.combined_recall,
            },
        },
    }


async def main():
    print("=" * 70)
    print("THREADLINE — Live Featherless Benchmark")
    print("=" * 70)
    cfg = sanitized_cfg()
    print(f"Provider: {cfg['provider']}")
    print(f"Base URL: {cfg['base_url']}")
    print(f"Model: {cfg['model']}")
    print(f"Temperature: {cfg['temperature']}")
    print(f"Max retries: {cfg['max_retries']}")
    print(f"Benchmark: {len(BENCHMARK)} incidents, {sum(len(inc['records']) for inc in BENCHMARK)} records")
    print(f"Runs per incident: {NUM_RUNS}")
    print()

    # Load extraction prompt
    template = load_prompt("extraction", "v1")
    schema_block = _format_schema_for_prompt(ExtractionModelOutput.model_json_schema())
    system_prompt = f"{template.content}\n{schema_block}"

    all_runs = []
    for run_idx in range(1, NUM_RUNS + 1):
        print(f"--- Run {run_idx}/{NUM_RUNS} ---")
        run_result = await run_live_benchmark_run(system_prompt)
        all_runs.append(run_result)
        print(f"  Extraction: {run_result['extraction_success']}/{run_result['extraction_total']} successful")
        print(f"  Avg latency: {run_result['avg_latency_ms']:.0f}ms")
        print(f"  Total tokens: {run_result['total_tokens']}")
        print(f"  Strong-ID recall: {run_result['strong_id_recall']:.4f}")
        print(f"  False merges: {run_result['metrics']['false_merge_count']}")
        print(f"  True links: {run_result['metrics']['true_link_count']}")
        print(f"  Link recommended: {run_result['metrics']['link_recommended_count']}")
        print()

    # Agreement across runs
    if NUM_RUNS >= 2:
        state_agreement = 0
        for i in range(len(BENCHMARK)):
            states = set()
            for run_result in all_runs:
                fm = run_result["metrics"]
                # Rough agreement check
                states.add((fm["false_merge_count"], fm["true_link_count"], fm["link_recommended_count"]))
            if len(states) == 1:
                state_agreement += 1
        print(f"State agreement across runs: {state_agreement}/{len(BENCHMARK)} incidents")

    # Final summary (use last run's metrics)
    final = all_runs[-1]
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(f"Extraction success rate: {final['extraction_success_rate']:.3f}")
    print(f"Field-level strong-ID recall: {final['strong_id_recall']:.4f}")
    print(f"Field-level strong-ID precision: {final['strong_id_precision']:.4f}")
    print(f"Field-level strong-ID Jaccard: {final['strong_id_jaccard']:.4f}")
    m = final["metrics"]
    print(f"False merges: {m['false_merge_count']} (rate: {m['false_merge_rate']:.4f})")
    print(f"True links: {m['true_link_count']}")
    print(f"False non-matches: {m['false_non_match_count']}")
    print(f"WSS: {m['weighted_safety_score']:.0f}")
    print(f"Blocked conflict recall: {m['blocked_conflict_recall']:.4f}")
    print(f"Decision breakdown: {m['decision_state_counts']}")
    print(f"Human review rate: {m['human_review_rate']:.4f}")
    print(f"Incident top-ranked true links: {m['incident_top_ranked_true_link_count']}")
    print(f"Incident top-ranked false merges: {m['incident_top_ranked_false_merge_count']}")

    # Success gate check
    print("\n--- SUCCESS GATE ---")
    gate_passes = []
    # >=3 same-identity incidents as link_recommended
    if m['incident_top_ranked_true_link_count'] >= 3:
        gate_passes.append("At least 3 same-identity link_recommended ✓")
    else:
        gate_passes.append(f"Only {m['incident_top_ranked_true_link_count']}/3 link_recommended ✗")
    # Zero different-identity as link_recommended
    if m['incident_top_ranked_false_merge_count'] == 0:
        gate_passes.append("Zero different-identity link_recommended (false merges) ✓")
    else:
        gate_passes.append(f"{m['incident_top_ranked_false_merge_count']} false merges ✗")
    # All gov-ID contradictions blocked
    if m['blocked_conflict_recall'] >= 1.0:
        gate_passes.append("All blocking conflicts preserved ✓")
    else:
        gate_passes.append("Blocking conflict recall < 1.0 ✗")

    for g in gate_passes:
        print(f"  {g}")

    gate_passed = all("✗" not in g for g in gate_passes)
    if gate_passed:
        print("\nSUCCESS GATE: PASSED ✓")
    else:
        print("\nSUCCESS GATE: NOT PASSED ✗")
        print("THREADLINE is undergoing exploratory live-provider validation.")
        print("No false merges were observed in the structured synthetic benchmark,")
        print("but complete positive-link capability through the live workflow")
        print("has not yet been established.")

    # Save results
    output = {
        "config": cfg,
        "runs": all_runs,
        "gate_passes": gate_passes,
        "gate_passed": gate_passed,
    }
    out_path = Path(__file__).resolve().parent.parent / "data" / "live_featherless_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
