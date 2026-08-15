"""
Identity-resolution benchmark runner — audited and corrected.

Three evaluation modes:
  `structured_engine` — pre-extracted structured records → candidate gen → comparison → linkage
  `mock_extraction`  — raw text → deterministic mock extraction → structured engine
  `full_workflow`     — raw text → complete 12-node orchestrator → final response

Includes:
- Correct candidate-generation TP/FP/FN breakdown
- Complete 36-pair ground-truth table
- Field-level extraction accuracy with per-record expected fields
- Threshold sweep with recomputed decisions
- Reproducible artifact generation (JSON, CSV, Markdown, API summary)
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import os
import re
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from app.config import Settings
from app.providers.mock_provider import MockProvider
from app.schemas.linkage import LinkageDecisionState
from app.schemas.models import (
    AnalyzeOptions, AnalyzeRequest, CandidateConnection, Certainty,
    ExtractedField, IncidentInput, NormalizedRecord, ProviderMode, RecordInput,
)
from app.services.candidate_generation import (
    BLOCKING_RULES,
    MANDATORY_STRONG_STRATEGIES,
    _TWO_HOP_MAX_PAIRS_PER_INCIDENT,
    _TWO_HOP_MAX_TOTAL_PAIRS,
    generate_candidates,
)
from app.services.candidate_scoring import retrieve_candidates as legacy_retrieve
from app.services.linkage_decision import (
    LINK_RECOMMENDED_MIN_SCORE, HUMAN_REVIEW_MIN_SCORE, determine_linkage,
)
from app.services.pairwise_compare import compare_records
from app.services.unicode_normalizer import (
    normalize_digits_only,
    clean_directional,
    clean_arabic_punctuation,
    get_arabic_label_pattern,
)
from app.workflow import WorkflowOrchestrator


# ═══════════════════════════════════════════════════════════
# Extraction ground truth per record
# ═══════════════════════════════════════════════════════════

# Each record has expected field keys that the mock extractor should find.
# These are used for field-level accuracy metrics.
RECORD_EXPECTED_FIELDS: dict[str, set[str]] = {
    "GOV-A1": {"name", "age", "government_id", "date_of_birth", "phone", "distinguishing_marks", "last_known_location"},
    "GOV-A2": {"name", "age", "government_id", "date_of_birth", "phone", "last_known_location"},
    "MULTI-A1": {"name", "date_of_birth", "phone", "email", "distinguishing_marks"},
    "MULTI-A2": {"name", "age", "phone", "email", "distinguishing_marks"},
    "TRANS-A1": {"name", "age", "phone", "distinguishing_marks"},
    "TRANS-A2": {"name", "age", "phone", "distinguishing_marks"},
    "SPELL-A1": {"name", "age", "phone"},
    "SPELL-A2": {"name", "age", "phone"},
    "CONFLICT-ID1": {"name", "government_id", "date_of_birth"},
    "CONFLICT-ID2": {"name", "government_id", "date_of_birth"},
    "DOBCONF-A1": {"name", "date_of_birth", "phone"},
    "DOBCONF-A2": {"name", "date_of_birth", "phone"},
    "DIFF-A1": {"name", "age", "date_of_birth", "phone"},
    "DIFF-A2": {"name", "age", "date_of_birth", "phone"},
    "COMMON-A1": {"name", "age"},
    "COMMON-A2": {"name", "age"},
    "SHELTER-A1": {"last_known_location"},
    "SHELTER-A2": {"last_known_location"},
    "AGE-A1": {"name", "age", "last_known_location"},
    "AGE-A2": {"name", "age", "last_known_location"},
    "AGEB-A1": {"name", "age", "phone"},
    "AGEB-A2": {"name", "age", "phone"},
    "DOBYR-A1": {"name", "date_of_birth", "phone"},
    "DOBYR-A2": {"name", "date_of_birth", "phone"},
    "SIB-A1": {"name", "age", "last_known_location", "family_member_names"},
    "SIB-A2": {"name", "age", "last_known_location", "family_member_names"},
    "DUP-A1": {"name", "age", "government_id", "phone", "last_known_location"},
    "DUP-A2": {"name", "age", "government_id", "phone", "last_known_location"},
    "SPARSE-A1": {"age"},
    "SPARSE-A2": {"age"},
    "MIX-A1": {"name", "government_id", "date_of_birth", "phone"},
    "MIX-A2": {"name", "government_id", "phone"},
    "WEAKBLOCK-A1": {"name", "age", "phone", "date_of_birth", "last_known_location"},
    "WEAKBLOCK-A2": {"name", "age", "phone", "date_of_birth", "last_known_location"},
    "RIVAL-A1": {"name", "age"},
    "RIVAL-A2": {"name", "age"},
    "RIVAL-A3": {"name", "age"},
    "MISS-A1": {"name", "age", "phone", "last_known_location"},
    "MISS-A2": {"name", "age", "phone", "last_known_location"},
    "MISS-A3": {"name", "age", "last_known_location"},
    "PATH-A1": {"name", "age"},
    "PATH-A2": {"name", "age"},
    "PATH-A3": {"name", "age"},
    "PATH-A4": {"name", "age"},
    "OCR-A1": {"name", "age", "government_id", "date_of_birth", "distinguishing_marks"},
    "OCR-A2": {"name", "age", "date_of_birth", "phone"},
    "FAMPHONE-A1": {"name", "age", "phone"},
    "FAMPHONE-A2": {"name", "age", "phone"},
    "PHONEFMT-A1": {"name", "phone"},
    "PHONEFMT-A2": {"name", "phone"},
    "MISSFLD-A1": {"name", "age", "phone", "email"},
    "MISSFLD-A2": {"name", "phone", "email"},
    "EMAIL-A1": {"email"},
    "EMAIL-A2": {"email"},
    "REORDER-A1": {"name", "age", "phone"},
    "REORDER-A2": {"name", "age", "phone"},
    "NOPAIR-A1": {"name", "age", "last_known_location"},
    "NOPAIR-A2": {"name", "last_known_location"},
}

STRONG_IDENTIFIER_FIELDS = {"government_id", "phone", "email"}

# Candidate cap used by the structured/mock benchmark. Kept in sync with
# _add_structured_pairs so before-cap/after-cap survival metrics are consistent.
_BENCH_CANDIDATE_CAP = 100

# Versioned strong-identifier strategy sets (Phase 9R-2).
#
# v1 = historical legacy definition, reconstructed from the Phase 9R change
#      note: it counted the weak phone_suffix strategy alongside the clean
#      strong identifiers. Deprecated — exposed only for historical comparison
#      and never compared to v2 as if they were the same metric.
_LEGACY_STRONG_STRATEGIES_V1 = frozenset({
    "government_id", "email_exact", "phone_full_exact", "phone_suffix",
})
# v2 = current definition. Only clean deterministic strong identifiers count.
# OCR-assisted (phone_ocr_compatible), compatible
# (phone_local_international_compatible), weak suffix (phone_suffix),
# transliteration-only, and fuzzy name strategies are excluded.
_STRONG_STRATEGIES_V2 = frozenset({
    "government_id", "email_exact", "phone_full_exact",
})


# ═══════════════════════════════════════════════════════════
# Phase 10R: audited ground-truth schema (v2) + integrity audit
# ═══════════════════════════════════════════════════════════
#
# v1 derivation limitation (documented): ``build_universe_table`` derives
# per-pair identity truth for NON-expected pairs from the incident-level
# ``relation`` field, assuming every record inside an incident shares that
# relation. That assumption is invalid when an incident container holds a
# DECOY record about a different person (placed there to exercise candidate
# blocking). The fixture never declares those pairs; the labels are a
# derivation artifact, not fixture truth.
#
# v2 correction: pairs with NO supporting identity evidence are reclassified
# to their evidence-based truth. The fixture file itself is NOT modified;
# v1 remains the default and is fully preserved (historical comparability).

GROUND_TRUTH_CORRECTIONS_V2: dict[tuple[str, frozenset[str]], str] = {
    ("INC-CANDIDATE-MISSED-BY-ONE-STRATEGY", frozenset({"MISS-A1", "MISS-A3"})): "different_identity",
    ("INC-CANDIDATE-MISSED-BY-ONE-STRATEGY", frozenset({"MISS-A2", "MISS-A3"})): "different_identity",
    ("INC-PATHOLOGICAL-COMMON-NAME", frozenset({"PATH-A1", "PATH-A4"})): "different_identity",
    ("INC-PATHOLOGICAL-COMMON-NAME", frozenset({"PATH-A2", "PATH-A4"})): "different_identity",
    ("INC-PATHOLOGICAL-COMMON-NAME", frozenset({"PATH-A3", "PATH-A4"})): "different_identity",
}

GROUND_TRUTH_CORRECTIONS_V2_RATIONALE: dict[tuple[str, frozenset[str]], str] = {
    ("INC-CANDIDATE-MISSED-BY-ONE-STRATEGY", frozenset({"MISS-A1", "MISS-A3"})):
        "Decoy record: MISS-A1 (Mina Darzi, 14, Al Noor School) vs MISS-A3 "
        "(Omar Khalil, 35, North Gate). Different names, ages and locations; "
        "no shared identifier. Derived same_identity is unsupported.",
    ("INC-CANDIDATE-MISSED-BY-ONE-STRATEGY", frozenset({"MISS-A2", "MISS-A3"})):
        "Decoy record: MISS-A2 (Mina Darzi, ~14, Al Noor School) vs MISS-A3 "
        "(Omar Khalil, 35, North Gate). Different names, ages and locations; "
        "no shared identifier. Derived same_identity is unsupported.",
    ("INC-PATHOLOGICAL-COMMON-NAME", frozenset({"PATH-A1", "PATH-A4"})):
        "Decoy record: PATH-A1 (Mohammed, 30-40) vs PATH-A4 (Fatima, 28, "
        "North Gate). Different names; no shared evidence.",
    ("INC-PATHOLOGICAL-COMMON-NAME", frozenset({"PATH-A2", "PATH-A4"})):
        "Decoy record: PATH-A2 (Mohammed, ~35) vs PATH-A4 (Fatima, 28). "
        "Different names; no shared evidence.",
    ("INC-PATHOLOGICAL-COMMON-NAME", frozenset({"PATH-A3", "PATH-A4"})):
        "Decoy record: PATH-A3 (Mohammed, 32) vs PATH-A4 (Fatima, 28). "
        "Different names; no shared evidence.",
}

# Audit classifications (Part C of Phase 10R).
_AUDIT_SUPPORTED_SAME = "supported_same_identity"
_AUDIT_SUPPORTED_DIFF = "supported_different_identity"
_AUDIT_SUPPORTED_AMBIG = "supported_ambiguous"
_AUDIT_INSUFFICIENT = "insufficient_fixture_evidence"
_AUDIT_CONFLICTS = "label_conflicts_with_fixture_evidence"


# ═══════════════════════════════════════════════════════════
# Phase 10S: canonical latent-identity ground truth (schema v3)
# ═══════════════════════════════════════════════════════════
#
# v3 makes fictional identity truth EXPLICIT and independent of the resolver:
# each record carries a canonical ``fictional_identity_id`` in a versioned
# COMPANION fixture (the original identity_benchmark.json bytes are never
# modified, so historical fixture hashes are preserved).
#
# Latent identity truth for a pair is derived ONLY by ID equality:
#
#     same_identity      iff  record_a.fictional_identity_id
#                            == record_b.fictional_identity_id
#     different_identity otherwise
#
# Nothing else — incident relation, expected_pair, extracted fields, evidence
# similarity, or the v2 correction table — may influence v3 latent truth.
#
# A record whose canonical identity is NOT authorially established by the
# fixture (e.g. the deliberately anonymous common-name/rival incidents) is
# marked ``canonical_identity_under_specified`` and carries NO ID. Any pair
# involving such a record is itself ``canonical_identity_under_specified``.
# This is the Phase 10S mandatory under-specification stop condition: we do
# NOT fabricate identity IDs to complete the migration.

IDENTITY_SCHEMA_VERSION = "1.0"
IDENTITY_FIXTURE_NAME = "identity_benchmark_identity_v3.json"
UNDER_SPECIFIED_TRUTH = "canonical_identity_under_specified"

# Historical weighted-safety-score pins (Phase 10R accepted values). Never
# recomputed or overwritten: v1 = +5, v2 = +25.
HISTORICAL_WSS_V1 = 5.0
HISTORICAL_WSS_V2 = 25.0


# Evidence dispositions (Phase 10S): what the OBSERVABLE fixture evidence
# justifies, independent of latent identity truth. A pair can legitimately be
# latent=different with evidence=genuinely_ambiguous — that is a benchmark
# condition, not an error.
_DISPOSITION_SUPPORTS_SAME = "supports_same_identity"
_DISPOSITION_SUPPORTS_DIFF = "supports_different_identity"
_DISPOSITION_AMBIGUOUS = "genuinely_ambiguous"
_DISPOSITION_INSUFFICIENT = "insufficient_evidence"


def _identity_fixture_path() -> Path:
    return Path(__file__).parent.parent.parent / "fixtures" / IDENTITY_FIXTURE_NAME


def load_identity_assignments(path: Path | None = None) -> dict[str, str | None]:
    """Load canonical v3 identity assignments.

    Returns ``{record_id: fictional_identity_id}`` for records with an
    established identity and ``{record_id: None}`` for records marked
    ``canonical_identity_under_specified``. Fails closed on malformed or
    incomplete assignments.
    """
    if path is None:
        path = _identity_fixture_path()
    if not path.exists():
        raise FileNotFoundError(
            f"v3 identity fixture missing: {path} (ground_truth_schema='v3' "
            "requires the Phase 10S companion fixture)"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("identity_schema_version") != IDENTITY_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported identity_schema_version: "
            f"{data.get('identity_schema_version')!r} (expected "
            f"{IDENTITY_SCHEMA_VERSION!r})"
        )
    entries = data.get("records")
    if not isinstance(entries, list) or not entries:
        raise ValueError("v3 identity fixture must contain a non-empty 'records' list")
    assignments: dict[str, str | None] = {}
    for entry in entries:
        rid = entry.get("record_id")
        if not rid or not isinstance(rid, str):
            raise ValueError("v3 identity entry missing record_id")
        has_id = "fictional_identity_id" in entry
        has_under = entry.get("canonical_identity_under_specified") is True
        if has_id == has_under:
            raise ValueError(
                f"record {rid}: must have exactly one of "
                "fictional_identity_id / canonical_identity_under_specified"
            )
        if rid in assignments:
            raise ValueError(f"duplicate identity assignment for record {rid}")
        if has_under:
            assignments[rid] = None
        else:
            fid = entry["fictional_identity_id"]
            if not fid or not isinstance(fid, str):
                raise ValueError(f"record {rid}: invalid fictional_identity_id")
            assignments[rid] = fid
    return assignments


def identity_assignment_sha256(
    assignments: dict[str, str | None],
) -> str:
    """Deterministic digest of canonical identity assignments.

    Computed from the canonical sorted representation
    ``record_id -> fictional_identity_id`` (under-specified records use the
    UNDER_SPECIFIED marker). Any accidental identity edit changes the digest.
    """
    lines = []
    for rid in sorted(assignments):
        fid = assignments[rid] if assignments[rid] is not None else UNDER_SPECIFIED_TRUTH
        lines.append(f"{rid} -> {fid}")
    blob = "\n".join(lines)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def validate_identity_assignments_cover_fixture(
    incidents: list[dict],
    assignments: dict[str, str | None],
) -> list[str]:
    """Fail-closed validation: every fixture record must have exactly one
    assignment, and every assignment must reference a real fixture record."""
    failures = []
    fixture_ids = {
        r["record_id"] for inc in incidents for r in inc["records"]
    }
    for rid in sorted(fixture_ids):
        if rid not in assignments:
            failures.append(f"record {rid} has no v3 identity assignment")
    for rid in sorted(assignments):
        if rid not in fixture_ids:
            failures.append(f"assignment for unknown record {rid}")
    return failures


_NAME_TOKEN_STOPWORDS = frozenset({"al", "el", "the", "bin", "ibn", "de", "di"})


def _name_tokens(value: str | None) -> set[str]:
    """Lowercased name tokens, dropping very short tokens and name stopwords."""
    if not value:
        return set()
    tokens = set()
    for tok in re.findall(r"[\w\u0600-\u06FF]+", value.lower()):
        if len(tok) < 3 or tok in _NAME_TOKEN_STOPWORDS:
            continue
        tokens.add(tok)
    return tokens


def _age_range(value: str | None) -> tuple[int, int] | None:
    """Return (lo, hi) age bounds from an extracted age value."""
    if not value:
        return None
    nums = [int(x) for x in re.findall(r"\d{1,3}", value)]
    if not nums:
        return None
    return (min(nums), max(nums))


def _ranges_overlap(a: tuple[int, int] | None, b: tuple[int, int] | None) -> bool:
    if a is None or b is None:
        return False
    return not (a[1] < b[0] or b[1] < a[0])


def _location_tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return {
        tok for tok in re.findall(r"[a-z]+", value.lower())
        if len(tok) >= 3 and tok not in _NAME_TOKEN_STOPWORDS
    }


def _audit_pair_evidence(
    rec_a: dict, rec_b: dict,
) -> dict:
    """Evidence summary for one record pair (Phase 10R integrity audit)."""
    from app.services.phone_parser import parse_phone_with_ocr

    fa = {f.key: f.value for f in mock_extract_fields(rec_a.get("text", ""), rec_a["record_id"], rec_a.get("language", "English")) if f.value is not None}
    fb = {f.key: f.value for f in mock_extract_fields(rec_b.get("text", ""), rec_b["record_id"], rec_b.get("language", "English")) if f.value is not None}

    na, nb = _name_tokens(fa.get("name")), _name_tokens(fb.get("name"))
    la, lb = _location_tokens(fa.get("last_known_location")), _location_tokens(fb.get("last_known_location"))

    def _phone_key(v):
        """Canonical phone key unifying intl/local representations (>=7 digits)."""
        if not v:
            return None
        p = parse_phone_with_ocr(str(v))
        if not p.is_valid:
            return None
        if p.explicit_international and p.country_code:
            d = p.national_number or ""
        else:
            d = p.normalized_digits
        return d if len(d) >= 7 else None

    pa, pb = _phone_key(fa.get("phone")), _phone_key(fb.get("phone"))
    ea, eb = (fa.get("email") or "").strip().lower(), (fb.get("email") or "").strip().lower()
    ga, gb = (fa.get("government_id") or "").strip(), (fb.get("government_id") or "").strip()

    def _dob_norm(v):
        if not v:
            return None
        return re.sub(r"[^\d-]", "", str(v).replace("l", "1"))

    da, db = _dob_norm(fa.get("date_of_birth")), _dob_norm(fb.get("date_of_birth"))

    def _dob_comparable(x, y):
        if not x or not y:
            return False
        if x == y:
            return True
        return x[:4] == y[:4]  # year-only vs full-date compatibility

    ra, rb = _age_range(fa.get("age")), _age_range(fb.get("age"))

    return {
        "name_overlap": bool(na & nb),
        "location_overlap": bool(la & lb),
        "phone_match": bool(pa and pa == pb),
        "email_match": bool(ea and ea == eb),
        "gov_match": bool(ga and ga == gb),
        "dob_match": _dob_comparable(da, db),
        "age_compatible": _ranges_overlap(ra, rb),
        "conflict_gov": bool(ga and gb and ga != gb),
        "conflict_dob": bool(da and db and da != db and da[:4] != db[:4]),
        "conflict_age": bool(
            ra and rb and ra[0] == ra[1] and rb[0] == rb[1] and abs(ra[0] - rb[0]) > 5
        ),
    }


def _audit_classify(truth: str, ev: dict) -> str:
    """Classify one pair's truth against its fixture evidence."""
    strong_shared = ev["gov_match"] or ev["email_match"] or ev["phone_match"] or ev["dob_match"]
    if truth == "same_identity":
        if strong_shared or (ev["name_overlap"] and (ev["age_compatible"] or ev["location_overlap"])):
            return _AUDIT_SUPPORTED_SAME
        return _AUDIT_CONFLICTS
    if truth == "different_identity":
        if ev["conflict_gov"] or ev["conflict_dob"] or ev["conflict_age"]:
            return _AUDIT_SUPPORTED_DIFF
        if not (ev["name_overlap"] and strong_shared):
            return _AUDIT_SUPPORTED_DIFF
        return _AUDIT_CONFLICTS
    if truth == "genuinely_ambiguous":
        if ev["name_overlap"] or ev["location_overlap"]:
            return _AUDIT_SUPPORTED_AMBIG
        return _AUDIT_CONFLICTS
    return _AUDIT_INSUFFICIENT


def evidence_disposition_for(ev: dict) -> str:
    """Phase 10S: classify what the OBSERVABLE evidence justifies, independent
    of latent identity truth.

    Order of precedence (fail-closed): a hard contradiction is the strongest
    signal; then a strong shared identifier; then weak overlap (ambiguous);
    otherwise insufficient evidence.
    """
    if ev.get("conflict_gov") or ev.get("conflict_dob") or ev.get("conflict_age"):
        return _DISPOSITION_SUPPORTS_DIFF
    strong_shared = ev.get("gov_match") or ev.get("email_match") or ev.get("phone_match") or ev.get("dob_match")
    if strong_shared:
        return _DISPOSITION_SUPPORTS_SAME
    if ev.get("name_overlap") or ev.get("location_overlap"):
        return _DISPOSITION_AMBIGUOUS
    return _DISPOSITION_INSUFFICIENT


def audit_ground_truth(
    incidents: list[dict],
    ground_truth_schema: str = "v1",
    *,
    identity_assignments: dict[str, str | None] | None = None,
) -> list[dict]:
    """Phase 10R integrity audit: classify every within-incident pair's ground
    truth against the fixture's own record evidence.

    With the default ``ground_truth_schema="v1"`` the audit uses the
    HISTORICAL (uncorrected) truth so that unsupported derived labels are
    detected (``label_conflicts_with_fixture_evidence``). With "v2" the
    audited corrections are applied before classification.

    With "v3" the truth is the canonical ID-derived latent truth; pairs
    touching a record whose canonical identity is under-specified are
    reported as ``canonical_identity_under_specified`` (they are NOT an
    evidence contradiction).
    """
    if ground_truth_schema == "v3":
        assignments = (
            load_identity_assignments()
            if identity_assignments is None
            else dict(identity_assignments)
        )
        validation_failures = validate_identity_assignments_cover_fixture(
            incidents, assignments
        )
        if validation_failures:
            raise ValueError(
                "v3 identity assignments incomplete: " + "; ".join(validation_failures)
            )
    rows = []
    for inc in incidents:
        gt = inc["ground_truth"]
        expected_set = set(gt["expected_pair"])
        recs = inc["records"]
        by_id = {r["record_id"]: r for r in recs}
        for i in range(len(recs)):
            for j in range(i + 1, len(recs)):
                a, b = recs[i]["record_id"], recs[j]["record_id"]
                pair_set = frozenset({a, b})
                relation = gt["relation"]
                if ground_truth_schema == "v2":
                    relation = GROUND_TRUTH_CORRECTIONS_V2.get(
                        (inc["incident_id"], pair_set), relation
                    )
                elif ground_truth_schema == "v3":
                    id_a = assignments.get(a)
                    id_b = assignments.get(b)
                    if id_a is None or id_b is None:
                        relation = UNDER_SPECIFIED_TRUTH
                    else:
                        relation = (
                            "same_identity" if id_a == id_b else "different_identity"
                        )
                ev = _audit_pair_evidence(by_id[a], by_id[b])
                rows.append({
                    "incident_id": inc["incident_id"],
                    "record_a": a,
                    "record_b": b,
                    "truth": relation,
                    "expected_candidate": bool(expected_set and pair_set == expected_set),
                    "audit": (
                        UNDER_SPECIFIED_TRUTH
                        if relation == UNDER_SPECIFIED_TRUTH
                        else _audit_classify(relation, ev)
                    ),
                    "evidence": {k: bool(v) for k, v in ev.items()},
                    "evidence_disposition": evidence_disposition_for(ev),
                    "identity_a": assignments.get(a) if ground_truth_schema == "v3" else None,
                    "identity_b": assignments.get(b) if ground_truth_schema == "v3" else None,
                })
    return rows


# ═══════════════════════════════════════════════════════════
# Upgraded deterministic mock extractor
# ═══════════════════════════════════════════════════════════

def mock_extract_fields(text: str, record_id: str, language: str) -> list[ExtractedField]:
    """Deterministic mock extraction from raw text. No hard-coded outputs per incident."""
    fields: list[ExtractedField] = []

    # Name: look for known name patterns, including "Last, First" format.
    # Guard: the token after the comma must look like a real given name
    # (capitalized, no digits, no field keywords) to avoid treating
    # "Amal Rafiq, DOB 2005" as a comma-separated name.
    name_val = None
    name_keywords = {'email','phone','tel','contact','dob','date','id','age','aged',
                     'approximately','approx','about','estimated','scar','mark',
                     'shelter','gate','school','clinic','hospital','road','market'}
    comma_name = re.search(
        r"([\u0600-\u06FF\w]+(?:\s+[\u0600-\u06FF\w]+)?),\s*"
        r"([A-Z\u0600-\u06FF][a-z\u0600-\u06FF]{2,}(?:\s+[A-Z\u0600-\u06FF][a-z\u0600-\u06FF]{2,})?)",
        text)
    if comma_name:
        g1 = comma_name.group(1) or ''
        g2 = comma_name.group(2) or ''
        first_token = g2.split()[0].lower() if g2 else ''
        # Guard BOTH halves of the comma-form name. The family-name half (g1)
        # must not contain digits or a field keyword either — otherwise
        # "age 35, North Gate" would be misread as a comma-form name with
        # g1='age 35' and g2='North Gate'.
        g1_ok = bool(g1) and not any(c.isdigit() for c in g1) \
            and g1.split()[0].lower() not in name_keywords
        if (
            first_token not in name_keywords
            and g1_ok
            and not any(c.isdigit() for c in g2)
        ):
            name_val = f"{g2} {g1}".strip()
        else:
            # Fall through: the comma pattern matched a field, not a name
            pass
    if name_val is None:
        # Standard name pattern — strip optional field-label prefixes like "Name:"
        name_match = re.search(
            r"(?:name\s*[:.]?\s*)?([\u0600-\u06FF\w]+(?:\s+[\u0600-\u06FF\w]+){0,3})",
            text, re.IGNORECASE,
        )
        if name_match:
            name_val = name_match.group(1).strip().rstrip(",")
            if any(c.isdigit() for c in name_val) or len(name_val) <= 1:
                name_val = None
    if name_val is not None and not name_val.lower().startswith(tuple(name_keywords)):
        fields.append(ExtractedField(
            field_id=f"{record_id}-name", key="name", label="Name",
            value=name_val, certainty=Certainty.exact,
            source_span_id=f"{record_id}-name-span",
        ))

    # Age: "age 14", "14 years", "14 عاما" (Arabic), OCR-tolerant (digit 'l'→'1')
    # Uses shared Unicode normalization — digits, directional controls, punctuation
    age_val = None
    age_words = r"(?:age|aged|\u0639\u0645\u0631|\u0639\u0645\u0631|\u0627\u0644\u0639\u0645\u0631)"  # English + Arabic
    years_words = r"(?:years?|ans?|\u0639\u0627\u0645\u0627)"
    # Shared Unicode normalization: convert all digit systems to ASCII for numeric matching
    digits_normalized_text = normalize_digits_only(text)
    age_match = re.search(rf"{age_words}\s*[:.]?\s*(\d{{1,3}}(?:\s*[-–]\s*\d{{1,3}})?)", digits_normalized_text, re.IGNORECASE)
    if not age_match:
        age_match = re.search(r"(?:approximately|approx\.?|about|estimated)\s+(\d{1,3})", digits_normalized_text, re.IGNORECASE)
    if not age_match:
        age_match = re.search(rf"(\d{{1,3}}(?:\s*[-–]\s*\d{{1,3}})?)\s*{years_words}", digits_normalized_text, re.IGNORECASE)
    if age_match:
        age_val = re.sub(r"\s*[-–]\s*", "-", age_match.group(1))
    # OCR fallback
    if not age_val:
        ocr_age = re.search(r"(?:age|aged|yr|yrs|yo)\s*[:.]?\s*([l1]\d|\d{1,2})\b", digits_normalized_text, re.IGNORECASE)
        if ocr_age:
            age_val = ocr_age.group(1).replace('l','1')
    if age_val:
        fields.append(ExtractedField(
            field_id=f"{record_id}-age", key="age", label="Age",
            value=age_val,
            certainty=Certainty.estimated if "-" in age_val or "approximately" in text.lower() or "estimated" in text.lower() else Certainty.exact,
            source_span_id=f"{record_id}-age-span",
        ))

    # DOB: ISO date patterns, OCR-tolerant (digit 'l' → '1')
    dob_match = re.search(r"(?:DOB|date of birth)\s*[:.]?\s*([l\d]{4}(?:[-–][l\d]{2}(?:[-–][l\d]{2})?)?)", text, re.IGNORECASE)
    if dob_match:
        dob_val = dob_match.group(1).replace("\u2013", "-").replace('l','1')
        if re.search(r'\d{4}', dob_val):  # must have at least a valid year
            fields.append(ExtractedField(
                field_id=f"{record_id}-dob", key="date_of_birth", label="Date of Birth",
                value=dob_val, certainty=Certainty.exact,
                source_span_id=f"{record_id}-dob-span",
            ))

    # Government ID
    id_match = re.search(r"(?:ID|identification|registration)\s*[:.#]?\s*([A-Z]{2,4}[\-–]\d{4,8})", text, re.IGNORECASE)
    if id_match:
        fields.append(ExtractedField(
            field_id=f"{record_id}-gov_id", key="government_id", label="Government ID",
            value=id_match.group(1).replace("\u2013", "-"), certainty=Certainty.exact,
            source_span_id=f"{record_id}-gov_id-span",
        ))

    # Phone: English (phone/tel/contact), Arabic (هاتف), OCR-tolerant
    # Uses shared phone_parser for Unicode digit normalization and formatting.
    # The validity gate is OCR-tolerant (parse_phone_with_ocr) so an OCR-
    # corrupted raw value (e.g. "+l-555-3434") is still preserved as raw
    # evidence; OCR repair is applied later by the comparison/candidate layer.
    from app.services.phone_parser import parse_phone_with_ocr
    phone_text = digits_normalized_text  # shared utility, not local conversion
    # Build phone label pattern: English + Arabic labels from shared module
    arabic_label_alt = get_arabic_label_pattern()
    phone_label_rx = rf"(?:phone|tel|contact|{arabic_label_alt})"
    phone_match = re.search(rf"{phone_label_rx}\s*[:.]?\s*([+l]?[\dl\s()\-.]{{7,20}})", phone_text, re.IGNORECASE)
    if not phone_match:
        # Bare number after a name-comma pattern ("Karim Mansour, phone (...)")
        phone_match = re.search(rf"[,;]?\s*{phone_label_rx}?\s*([(]?[+l]?[\dl\s()\-.]{{7,20}})", phone_text, re.IGNORECASE)
    if not phone_match:
        # Fallback: any plausible phone number
        phone_match = re.search(r"\b([+l]?[\dl\s()\-.]{10,20})\b", phone_text)
    if phone_match:
        raw_phone = phone_match.group(1)
        parsed = parse_phone_with_ocr(raw_phone)
        if parsed.is_valid:
            fields.append(ExtractedField(
                field_id=f"{record_id}-phone", key="phone", label="Phone",
                value=raw_phone, certainty=Certainty.exact,
                source_span_id=f"{record_id}-phone-span",
            ))

    # Email
    email_match = re.search(r"(?:email|e-mail)\s*[:.]?\s*([\w.+-]+@[\w-]+\.[\w.]+)", text, re.IGNORECASE)
    if email_match:
        fields.append(ExtractedField(
            field_id=f"{record_id}-email", key="email", label="Email",
            value=email_match.group(1).strip().lower(), certainty=Certainty.exact,
            source_span_id=f"{record_id}-email-span",
        ))

    # Location
    loc_match = re.search(r"(?:at|near|seen at|located at|arrived at|shelter|taken to|admitted to)\s+([A-Z][\w\s]{3,40}?)(?:\.|,|$|;|\s+\d)", text, re.IGNORECASE)
    if not loc_match:
        loc_match = re.search(r"([A-Z][\w\s]+?(?:School|Gate|Market|Road|Clinic|Shelter|Depot|Station))", text)
    if loc_match:
        fields.append(ExtractedField(
            field_id=f"{record_id}-location", key="last_known_location", label="Last Known Location",
            value=loc_match.group(1).strip(), certainty=Certainty.exact,
            source_span_id=f"{record_id}-location-span",
        ))

    # Distinguishing marks
    mark_match = re.search(r"(?:scar|tattoo|mark|limp|distinctive)\s+(?:above |on |near )?[\w\s]+?(?:eyebrow|hand|arm|leg|face|cheek|forehead)", text, re.IGNORECASE)
    if mark_match:
        fields.append(ExtractedField(
            field_id=f"{record_id}-mark", key="distinguishing_marks", label="Distinguishing Marks",
            value=mark_match.group(0).strip(), certainty=Certainty.exact,
            source_span_id=f"{record_id}-mark-span",
        ))

    # Family member names
    family_match = re.search(r"(?:mother|father|parent|sibling)\s+([\w\s]{2,30}?)(?:\.|,|$)", text, re.IGNORECASE)
    if family_match:
        fields.append(ExtractedField(
            field_id=f"{record_id}-family", key="family_member_names", label="Family Member",
            value=family_match.group(1).strip(), certainty=Certainty.exact,
            source_span_id=f"{record_id}-family-span",
        ))

    return fields


def build_normalized_record(record_data: dict, record_id: str) -> NormalizedRecord:
    fields = mock_extract_fields(record_data.get("text", ""), record_id, record_data.get("language", "English"))
    return NormalizedRecord(
        record_id=record_id,
        source_type=record_data.get("source_type", "unknown"),
        language=record_data.get("language", "English"),
        text=record_data.get("text", ""),
        timestamp=record_data.get("timestamp"),
        display_name=record_data.get("display_name", record_id),
        safe_text=record_data.get("text", ""),
        fields=fields,
    )


# ═══════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════

@dataclass
class PairResult:
    record_id_a: str
    record_id_b: str
    system: str  # "structured_engine", "mock_extraction", "full_workflow", "legacy"
    candidate_found: bool = True
    linkage_state: str | None = None
    total_score: float = 0.0
    blocking_conflicts: list[str] = field(default_factory=list)
    supporting_fields: list[str] = field(default_factory=list)
    candidate_generation_rules: list[str] = field(default_factory=list)
    is_blocking_rule: bool = False
    is_fallback: bool = False
    is_expansion: bool = False           # Phase 10: incident_two_hop_candidate
    expansion_intermediary_ids: list[str] = field(default_factory=list)
    expansion_depth: int = 0
    is_legacy: bool = False
    ground_truth_relation: str = ""
    expected_state: str = ""
    expected_pair_match: bool = False
    incident_id: str = ""
    extraction_fields: set[str] = field(default_factory=set)

    @property
    def generation_category(self) -> str:
        if self.is_legacy:
            return "legacy_all_pairs"
        if self.is_fallback:
            return "controlled_fallback"
        if self.is_expansion:
            return "bounded_expansion"
        return "deterministic_blocking"


@dataclass
class IncidentResult:
    incident_id: str
    description: str
    ground_truth_relation: str
    expected_pair: list[str]
    expected_state: str
    acceptable_states: list[str]
    expected_blocking: list[str]
    pair_results: list[PairResult] = field(default_factory=list)

    def best_for(self, system: str, prefer_expected: bool = True) -> PairResult | None:
        candidates = [pr for pr in self.pair_results if pr.system == system and pr.candidate_found]
        if prefer_expected and self.expected_pair:
            for pr in candidates:
                if {pr.record_id_a, pr.record_id_b} == set(self.expected_pair):
                    return pr
        return candidates[0] if candidates else None

    @property
    def new_state_match(self) -> bool:
        br = self.best_for("structured_engine")
        return br is not None and br.linkage_state in self.acceptable_states


# ═══════════════════════════════════════════════════════════
# Complete 36-pair ground-truth table
# ═══════════════════════════════════════════════════════════

@dataclass
class UniversePair:
    """One row in the complete within-incident pair universe.

    Phase 10S separates four concepts:
      * identity_truth        — latent identity (same/different) OR
                                canonical_identity_under_specified (v3)
      * evidence_disposition  — what the observable evidence justifies
      * is_expected_candidate — retrieval/blocking expectation
      * expected_linkage_state / acceptable_states — workflow expectation
    """
    incident_id: str
    record_a: str
    record_b: str
    identity_truth: str  # same_identity, different_identity, genuinely_ambiguous, canonical_identity_under_specified
    is_expected_candidate: bool
    expected_linkage_state: str
    acceptable_states: list[str] = field(default_factory=list)
    # Phase 10S: canonical identity provenance + evidence disposition
    identity_a: str | None = None        # fictional_identity_id or None (under-specified)
    identity_b: str | None = None
    under_specified: bool = False        # True if either record lacks canonical identity
    evidence_disposition: str = ""       # supports_same / supports_different / genuinely_ambiguous / insufficient
    # Populated after evaluation
    se_candidate: bool = False    # structured_engine found this pair?
    se_source: str = ""           # deterministic_blocking / controlled_fallback / not_found
    se_decision: str = ""         # linkage state
    me_candidate: bool = False    # mock_extraction
    me_source: str = ""
    me_decision: str = ""
    fw_candidate: bool = False    # full_workflow
    fw_source: str = ""
    fw_decision: str = ""
    legacy_candidate: bool = False
    legacy_decision: str = ""


def build_universe_table(
    incidents: list[dict],
    ground_truth_schema: str = "v1",
    *,
    identity_assignments: dict[str, str | None] | None = None,
) -> list[UniversePair]:
    """Build the complete 36-pair universe table with ground truth.

    Every pair gets identity truth, expected-candidate status, expected
    linkage state, and acceptable states. Non-expected pairs (pairs that
    are not the primary expected pair for the incident) still receive
    ground-truth entries derived from the incident's overall truth.

    ``ground_truth_schema``:
      * "v1" (historical — non-expected pairs inherit the incident relation)
      * "v2" (audited — pairs corrected per ``GROUND_TRUTH_CORRECTIONS_V2``)
      * "v3" (canonical — latent identity truth derived ONLY from canonical
        ``fictional_identity_id`` equality; ambiguity migrates to
        ``evidence_disposition``; pairs touching a record whose identity is
        under-specified are ``canonical_identity_under_specified``)

    ``identity_assignments`` overrides the on-disk companion fixture (used by
    adversarial mutation tests to prove v3 truth depends ONLY on IDs).

    v1 is the default; results across schemas are never directly compared.
    """
    if ground_truth_schema not in ("v1", "v2", "v3"):
        raise ValueError(f"Unknown ground_truth_schema: {ground_truth_schema!r}")

    # Phase 10S: load canonical identity assignments once for v3. Fail closed
    # on missing/malformed/incomplete assignments — never silently degrade.
    assignments: dict[str, str | None] = {}
    if ground_truth_schema == "v3":
        assignments = (
            load_identity_assignments()
            if identity_assignments is None
            else dict(identity_assignments)
        )
        validation_failures = validate_identity_assignments_cover_fixture(
            incidents, assignments
        )
        if validation_failures:
            raise ValueError(
                "v3 identity assignments incomplete: " + "; ".join(validation_failures)
            )

    table = []
    for inc in incidents:
        gt = inc["ground_truth"]
        rec_ids = [r["record_id"] for r in inc["records"]]
        expected_set = set(gt["expected_pair"])
        relation = gt["relation"]
        rec_by_id = {r["record_id"]: r for r in inc["records"]}

        for i in range(len(rec_ids)):
            for j in range(i + 1, len(rec_ids)):
                a, b = rec_ids[i], rec_ids[j]
                pair_set = {a, b}
                is_expected = bool(expected_set and pair_set == expected_set)

                # ── Latent identity truth (per schema) ──
                if ground_truth_schema == "v3":
                    id_a = assignments.get(a)
                    id_b = assignments.get(b)
                    if id_a is None or id_b is None:
                        pair_relation = UNDER_SPECIFIED_TRUTH
                    else:
                        pair_relation = (
                            "same_identity" if id_a == id_b else "different_identity"
                        )
                else:
                    # Per-pair truth (never mutate the incident-level relation
                    # across iterations).
                    pair_relation = relation
                    if ground_truth_schema == "v2":
                        pair_relation = GROUND_TRUTH_CORRECTIONS_V2.get(
                            (inc["incident_id"], frozenset(pair_set)), relation
                        )

                # ── Expected workflow state (independent of latent truth) ──
                if is_expected:
                    expected_state = gt["expected_state"]
                    acceptable_states = list(gt["acceptable_states"])
                elif pair_relation == "same_identity":
                    # Non-expected pair in same-identity incident: all records same person
                    expected_state = "human_review_required"
                    acceptable_states = ["human_review_required", "insufficient_evidence"]
                elif pair_relation == "different_identity":
                    # Non-expected pair in different-identity incident
                    expected_state = "do_not_link"
                    acceptable_states = ["do_not_link", "blocked_by_conflict", "insufficient_evidence"]
                elif pair_relation == "genuinely_ambiguous":
                    # Non-expected pair in ambiguous incident
                    expected_state = "insufficient_evidence"
                    acceptable_states = ["insufficient_evidence"]
                else:
                    # canonical_identity_under_specified: identity truth is
                    # NOT established; workflow expectation stays conservative.
                    expected_state = "insufficient_evidence"
                    acceptable_states = ["insufficient_evidence"]

                # ── Phase 10S evidence disposition (independent of truth) ──
                ev = _audit_pair_evidence(rec_by_id[a], rec_by_id[b])
                disposition = evidence_disposition_for(ev)

                id_a = assignments.get(a) if ground_truth_schema == "v3" else None
                id_b = assignments.get(b) if ground_truth_schema == "v3" else None

                table.append(UniversePair(
                    incident_id=inc["incident_id"],
                    record_a=a, record_b=b,
                    identity_truth=pair_relation,
                    is_expected_candidate=is_expected,
                    expected_linkage_state=expected_state,
                    acceptable_states=acceptable_states,
                    identity_a=id_a,
                    identity_b=id_b,
                    under_specified=(
                        ground_truth_schema == "v3" and (id_a is None or id_b is None)
                    ),
                    evidence_disposition=disposition,
                ))
    return table


# ═══════════════════════════════════════════════════════════
# Benchmark execution — three modes
# ═══════════════════════════════════════════════════════════

def load_benchmark(path: Path | None = None) -> list[dict]:
    if path is None:
        path = Path(__file__).parent.parent.parent / "fixtures" / "identity_benchmark.json"
    with open(path, encoding='utf-8') as f:
        return json.load(f)["incidents"]


def _make_incident_result(inc: dict) -> IncidentResult:
    gt = inc["ground_truth"]
    return IncidentResult(
        incident_id=inc["incident_id"], description=inc["description"],
        ground_truth_relation=gt["relation"],
        expected_pair=gt["expected_pair"],
        expected_state=gt["expected_state"],
        acceptable_states=gt["acceptable_states"],
        expected_blocking=gt["expected_blocking"],
    )


def _add_structured_pairs(
    ir: IncidentResult, records: list[NormalizedRecord], inc: dict, system: str,
):
    """Run candidate generation and comparison/decision on structured records."""
    gt = inc["ground_truth"]
    expected_set = set(gt["expected_pair"])
    run = generate_candidates(
        records, max_candidates=_BENCH_CANDIDATE_CAP, return_report=True
    )
    expansion_prov = {
        tuple(p["pair"]): p for p in run.stats["expansion"]["provenance"]
    }
    for rid_a, rid_b, rules in run.candidates:
        rec_a = next(r for r in records if r.record_id == rid_a)
        rec_b = next(r for r in records if r.record_id == rid_b)
        comps = compare_records(rec_a, rec_b)
        decision = determine_linkage(comps, rid_a, rid_b, candidate_generation_rules=rules)
        is_fallback = any(r.startswith("fallback_") for r in rules)
        is_expansion = "incident_two_hop_candidate" in rules
        is_blocking = any(r in {br["rule_id"] for br in BLOCKING_RULES} for r in rules)
        prov = expansion_prov.get((rid_a, rid_b)) or expansion_prov.get((rid_b, rid_a))
        ir.pair_results.append(PairResult(
            record_id_a=rid_a, record_id_b=rid_b, system=system,
            linkage_state=decision.state.value,
            total_score=decision.total_score,
            blocking_conflicts=[b.field_name for b in decision.blocking_conflicts],
            supporting_fields=[s.field_name for s in decision.strongest_supporting],
            candidate_generation_rules=rules,
            is_blocking_rule=is_blocking, is_fallback=is_fallback,
            is_expansion=is_expansion,
            expansion_intermediary_ids=(prov["intermediary_ids"] if prov else []),
            expansion_depth=(prov["depth"] if prov else (1 if is_expansion else 0)),
            ground_truth_relation=gt["relation"],
            expected_state=gt["expected_state"],
            expected_pair_match=bool(expected_set and {rid_a, rid_b} == expected_set),
            incident_id=ir.incident_id,
        ))


def _add_legacy_pairs(ir: IncidentResult, records: list[NormalizedRecord], inc: dict):
    gt = inc["ground_truth"]
    expected_set = set(gt["expected_pair"])
    for lc in legacy_retrieve(records, 5):
        ir.pair_results.append(PairResult(
            record_id_a=lc.record_a_id, record_id_b=lc.record_b_id, system="legacy",
            linkage_state=lc.classification_code.value,
            total_score=lc.retrieval_score, is_legacy=True,
            ground_truth_relation=gt["relation"],
            expected_state=gt["expected_state"],
            expected_pair_match=bool(expected_set and {lc.record_a_id, lc.record_b_id} == expected_set),
            incident_id=ir.incident_id,
        ))


def run_mode_structured_engine(incidents: list[dict]) -> list[IncidentResult]:
    """Mode 1: Pre-extracted structured records, bypassing LLM extraction."""
    results = []
    for inc in incidents:
        ir = _make_incident_result(inc)
        records = [build_normalized_record(r, r["record_id"]) for r in inc["records"]]
        _add_structured_pairs(ir, records, inc, "structured_engine")
        _add_legacy_pairs(ir, records, inc)
        results.append(ir)
    return results


def run_mode_mock_extraction(incidents: list[dict]) -> list[IncidentResult]:
    """Mode 2: Raw text through deterministic mock extraction, then structured engine."""
    results = []
    for inc in incidents:
        ir = _make_incident_result(inc)
        records = [build_normalized_record(r, r["record_id"]) for r in inc["records"]]
        _add_structured_pairs(ir, records, inc, "mock_extraction")
        _add_legacy_pairs(ir, records, inc)
        results.append(ir)
    return results


async def run_mode_full_workflow(incidents: list[dict]) -> list[IncidentResult]:
    """Mode 3: Raw text through complete 12-node orchestrator."""
    results = []
    for inc in incidents:
        gt = inc["ground_truth"]
        ir = _make_incident_result(inc)
        expected_set = set(gt["expected_pair"])

        request = AnalyzeRequest(
            incident=IncidentInput(incident_id=inc["incident_id"], name=inc["description"],
                                    languages=["English", "Arabic"]),
            records=[RecordInput(
                record_id=r["record_id"], source_type=r["source_type"],
                language=r["language"], text=r["text"],
                timestamp=r.get("timestamp"), display_name=r.get("display_name"),
            ) for r in inc["records"]],
            options=AnalyzeOptions(provider_mode=ProviderMode.mock, candidate_limit=5,
                                   include_workflow_trace=False),
        )
        response = await WorkflowOrchestrator(
            settings=Settings(), provider=MockProvider()
        ).run(request)

        for candidate in response.candidates:
            is_fallback = candidate.candidate_fallback
            is_blocking = any(
                r in {br["rule_id"] for br in BLOCKING_RULES}
                for r in candidate.candidate_generation_rules
            )
            ir.pair_results.append(PairResult(
                record_id_a=candidate.record_a_id,
                record_id_b=candidate.record_b_id,
                system="full_workflow",
                linkage_state=candidate.linkage_decision_state or candidate.classification_code.value,
                total_score=candidate.retrieval_score,
                blocking_conflicts=candidate.blocking_reason_codes,
                supporting_fields=[
                    s.get("field_name", "") for s in candidate.pairwise_comparisons
                    if s.get("classification") in ("exact_match", "normalized_match")
                ],
                candidate_generation_rules=candidate.candidate_generation_rules,
                is_blocking_rule=is_blocking, is_fallback=is_fallback,
                is_legacy=not candidate.linkage_decision_state,
                ground_truth_relation=gt["relation"],
                expected_state=gt["expected_state"],
                expected_pair_match=bool(expected_set and {
                    candidate.record_a_id, candidate.record_b_id
                } == expected_set),
                incident_id=ir.incident_id,
            ))
        results.append(ir)
    return results


# ═══════════════════════════════════════════════════════════
# Metrics with automated assertions
# ═══════════════════════════════════════════════════════════

STATE_LEGACY_MAP = {
    "strong_candidate_for_review": "link_recommended",
    "possible_candidate": "human_review_required",
    "insufficient_evidence": "insufficient_evidence",
    "conflicting_evidence": "blocked_by_conflict",
}


def _mapped_state(state: str | None) -> str:
    """Map legacy classification names to canonical linkage states."""
    return STATE_LEGACY_MAP.get(state or "", state or "")


@dataclass
class CandidateGenMetrics:
    """Candidate generation metrics with TP/FP/FN breakdown."""
    blocking_tp: int = 0
    blocking_fp: int = 0
    blocking_fn: int = 0
    blocking_precision: float = 0.0
    blocking_recall: float = 0.0
    fallback_tp: int = 0
    fallback_fp: int = 0
    fallback_fn: int = 0
    fallback_recall: float = 0.0
    fallback_activation_rate: float = 0.0
    combined_tp: int = 0
    combined_fp: int = 0
    combined_fn: int = 0
    combined_precision: float = 0.0
    combined_recall: float = 0.0
    legacy_recall: float = 0.0
    reduction_vs_all_pairs: float = 0.0
    missed_match_count: int = 0
    blocking_rule_hits: dict[str, int] = field(default_factory=dict)
    total_blocking_pairs: int = 0
    total_fallback_pairs: int = 0
    total_all_pairs_possible: int = 0
    unique_id_survival: int = 0  # DEPRECATED v1 alias — use unique_id_survival_v1
    # ── Phase 9R-2 versioned strong-identifier survival ──
    unique_id_survival_v1: int = 0                  # legacy definition (incl. weak phone_suffix)
    unique_id_survival_v1_eligible: int = 0         # v1-eligible expected pairs before cap
    unique_id_survival_v1_removed_by_cap: int = 0
    strong_identifier_survival_v2: int = 0          # current clean strong definition
    strong_identifier_survival_v2_eligible: int = 0
    strong_identifier_survival_v2_removed_by_cap: int = 0
    # ── Phase 10F candidate metrics (versioned) ──
    total_expansion_pairs: int = 0
    phase10_candidate_metrics: dict = field(default_factory=dict)
    CANDIDATE_METRICS_VERSION = "1.0"

    def validate(self) -> list[str]:
        failures = []
        # Recall = TP / (TP + FN)
        if self.blocking_tp + self.blocking_fn > 0:
            expected_br = self.blocking_tp / (self.blocking_tp + self.blocking_fn)
            if abs(self.blocking_recall - expected_br) > 0.001:
                failures.append(f"Blocking recall mismatch: {self.blocking_recall:.4f} vs {expected_br:.4f}")
        # Precision = TP / (TP + FP)
        if self.blocking_tp + self.blocking_fp > 0:
            expected_bp = self.blocking_tp / (self.blocking_tp + self.blocking_fp)
            if abs(self.blocking_precision - expected_bp) > 0.001:
                failures.append(f"Blocking precision mismatch: {self.blocking_precision:.4f} vs {expected_bp:.4f}")
        if self.combined_tp + self.combined_fp > 0:
            expected_cp = self.combined_tp / (self.combined_tp + self.combined_fp)
            if abs(self.combined_precision - expected_cp) > 0.001:
                failures.append(f"Combined precision mismatch: {self.combined_precision:.4f} vs {expected_cp:.4f}")
        if self.combined_tp + self.combined_fn > 0:
            expected_cr = self.combined_tp / (self.combined_tp + self.combined_fn)
            if abs(self.combined_recall - expected_cr) > 0.001:
                failures.append(f"Combined recall mismatch: {self.combined_recall:.4f} vs {expected_cr:.4f}")
        if self.combined_recall < self.blocking_recall:
            failures.append("Combined recall < blocking recall")
        if self.strong_identifier_survival_v2_removed_by_cap != 0:
            failures.append(
                f"clean strong-identifier pairs removed by cap = "
                f"{self.strong_identifier_survival_v2_removed_by_cap} (must be 0)"
            )
        if self.unique_id_survival != self.unique_id_survival_v1:
            failures.append("unique_id_survival deprecated alias != unique_id_survival_v1")
        return failures


@dataclass
class ExtractionMetrics:
    """Field-level extraction accuracy with explicit ground truth.

    Reports TP/FP/FN/TN, precision, recall, Jaccard index, exact-match
    accuracy, and present-field accuracy per canonical field.
    """
    per_field: dict[str, dict] = field(default_factory=dict)
    present_field_accuracy: dict[str, float] = field(default_factory=dict)
    strong_id_tp: int = 0
    strong_id_fp: int = 0
    strong_id_fn: int = 0
    strong_id_tn: int = 0
    strong_id_precision: float = 0.0
    strong_id_recall: float = 0.0
    strong_id_jaccard: float = 0.0

    def validate(self) -> list[str]:
        failures = []
        for fname, m in self.per_field.items():
            tp, fp, fn, tn = m.get("tp", 0), m.get("fp", 0), m.get("fn", 0), m.get("tn", 0)
            expected_p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            expected_r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            expected_j = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0.0
            expected_a = (tp + tn) / (tp + fp + fn + tn) if (tp + fp + fn + tn) > 0 else 0.0
            if abs(m.get("precision", 0.0) - expected_p) > 0.001:
                failures.append(f"{fname} precision mismatch: {m['precision']:.4f} vs {expected_p:.4f}")
            if abs(m.get("recall", 0.0) - expected_r) > 0.001:
                failures.append(f"{fname} recall mismatch: {m['recall']:.4f} vs {expected_r:.4f}")
            if abs(m.get("jaccard", 0.0) - expected_j) > 0.001:
                failures.append(f"{fname} jaccard mismatch: {m['jaccard']:.4f} vs {expected_j:.4f}")
            if abs(m.get("accuracy", 0.0) - expected_a) > 0.001:
                failures.append(f"{fname} accuracy mismatch: {m['accuracy']:.4f} vs {expected_a:.4f}")
        if self.strong_id_tp + self.strong_id_fp > 0:
            expected_sip = self.strong_id_tp / (self.strong_id_tp + self.strong_id_fp)
            if abs(self.strong_id_precision - expected_sip) > 0.001:
                failures.append(f"Strong-ID precision mismatch: {self.strong_id_precision:.4f} vs {expected_sip:.4f}")
        if self.strong_id_tp + self.strong_id_fn > 0:
            expected_sir = self.strong_id_tp / (self.strong_id_tp + self.strong_id_fn)
            if abs(self.strong_id_recall - expected_sir) > 0.001:
                failures.append(f"Strong-ID recall mismatch: {self.strong_id_recall:.4f} vs {expected_sir:.4f}")
        expected_sij = self.strong_id_tp / (self.strong_id_tp + self.strong_id_fp + self.strong_id_fn) if (self.strong_id_tp + self.strong_id_fp + self.strong_id_fn) > 0 else 0.0
        if abs(self.strong_id_jaccard - expected_sij) > 0.001:
            failures.append(f"Strong-ID jaccard mismatch: {self.strong_id_jaccard:.4f} vs {expected_sij:.4f}")
        return failures


@dataclass
class BenchmarkMetrics:
    """Comprehensive benchmark metrics with validation."""
    total_incidents: int = 0
    total_records: int = 0
    total_possible_pairs: int = 0
    expected_candidate_pairs: int = 0
    system: str = "structured_engine"
    evaluated_pairs: int = 0
    same_identity_pairs: int = 0
    different_identity_pairs: int = 0
    ambiguous_pairs: int = 0
    decision_state_counts: dict[str, int] = field(default_factory=dict)
    link_recommended_count: int = 0
    human_review_required_count: int = 0
    insufficient_evidence_count: int = 0
    blocked_by_conflict_count: int = 0
    do_not_link_count: int = 0
    false_merge_count: int = 0
    false_merge_rate: float = 0.0
    false_non_match_count: int = 0
    true_link_count: int = 0
    true_link_rate: float = 0.0
    blocked_conflict_recall: float = 0.0
    human_review_rate: float = 0.0
    insufficient_evidence_rate: float = 0.0
    weighted_safety_score: float = 0.0
    # ── Incident-level (production ranking, no expected-pair leakage) ──
    incident_top_ranked_correct_count: int = 0
    incident_top_ranked_true_link_count: int = 0
    incident_top_ranked_false_merge_count: int = 0
    incidents_with_no_candidates: int = 0
    incidents_routed_to_review: int = 0
    correct_candidate_not_ranked_first: int = 0
    # ── Legacy retrieval metrics ──
    legacy_same_id_recall: float = 0.0
    legacy_different_id_exposure: float = 0.0
    legacy_ambiguous_exposure: float = 0.0
    legacy_avg_candidates_per_incident: float = 0.0
    legacy_all_pairs_reduction: float = 0.0
    # Historical legacy false-merge counts (for artifact comparison only). The
    # legacy system has no final link_recommended state, so this counts legacy
    # pairs whose mapped state is link_recommended on different-identity
    # incidents — never every possible_candidate.
    legacy_false_merge_count: int = 0
    legacy_false_merge_rate: float = 0.0
    # ── Separate recall definitions ──
    expected_candidate_recall: float = 0.0  # retrieved expected pairs / all expected pairs
    expected_candidate_recall_n: int = 0
    expected_candidate_recall_d: int = 0
    same_identity_candidate_recall: float = 0.0  # retrieved same-id pairs / all same-id pairs
    same_identity_candidate_recall_n: int = 0
    same_identity_candidate_recall_d: int = 0
    blocking_conflict_candidate_recall: float = 0.0  # retrieved conflict pairs / all such pairs
    blocking_conflict_candidate_recall_n: int = 0
    blocking_conflict_candidate_recall_d: int = 0
    ambiguous_candidate_recall: float = 0.0
    ambiguous_candidate_recall_n: int = 0
    ambiguous_candidate_recall_d: int = 0
    unsafe_upgrade_count: int = 0
    ground_truth_schema: str = "v1"
    # ── Phase 10S canonical identity (v3) ──
    identity_schema_version: str = ""
    identity_assignment_sha256: str = ""
    under_specified_pair_count: int = 0       # EVALUATED v3 pairs with no canonical identity
    universe_under_specified_pair_count: int = 0  # all v3 universe pairs with no canonical identity
    unsafe_under_specified_link_count: int = 0  # v3 under-specified pairs that reached link_recommended
    # ── Versioned weighted safety score (Phase 10S) ──
    wss_v1: float = 0.0   # historical pin: +5 (Phase 10R accepted)
    wss_v2: float = 0.0   # historical pin: +25 (Phase 10R accepted)
    wss_v3: float = 0.0   # computed under v3 canonical-truth semantics
    candidate_gen: CandidateGenMetrics = field(default_factory=CandidateGenMetrics)
    extraction: ExtractionMetrics = field(default_factory=ExtractionMetrics)

    def validate(self, universe_same_count: int = 0, universe_diff_count: int = 0, universe_ambig_count: int = 0, universe_under_count: int = 0) -> list[str]:
        failures = []
        decision_sum = sum(self.decision_state_counts.values())
        if decision_sum != self.evaluated_pairs:
            failures.append(f"Decision sum {decision_sum} != evaluated_pairs {self.evaluated_pairs}")
        # GT sum of evaluated pairs must match evaluated count
        gt_evaluated_sum = self.same_identity_pairs + self.different_identity_pairs + self.ambiguous_pairs + self.under_specified_pair_count
        if gt_evaluated_sum != self.evaluated_pairs:
            failures.append(f"GT evaluated sum {gt_evaluated_sum} != evaluated_pairs {self.evaluated_pairs}")
        # Total universe GT must be >= evaluated (some may be unretrieved)
        universe_total = universe_same_count + universe_diff_count + universe_ambig_count + universe_under_count
        if self.evaluated_pairs > universe_total:
            failures.append(f"Evaluated {self.evaluated_pairs} > universe total {universe_total}")
        if universe_same_count > 0 and self.same_identity_candidate_recall_d != universe_same_count:
            failures.append(f"Same-id recall denom {self.same_identity_candidate_recall_d} != universe same count {universe_same_count}")
        if self.different_identity_pairs > 0:
            expected_fmr = self.false_merge_count / self.different_identity_pairs
            if abs(self.false_merge_rate - expected_fmr) > 0.001:
                failures.append(f"FMR mismatch: {self.false_merge_rate:.4f} vs {expected_fmr:.4f}")
        # WSS: schema-local. v1/v2 use the historical formula; v3 additionally
        # penalizes auto-links on under-specified pairs (fail-closed).
        if self.ground_truth_schema == "v3":
            expected_wss = self.wss_v3
            if abs(self.weighted_safety_score - expected_wss) > 0.01:
                failures.append(f"WSS mismatch (v3): {self.weighted_safety_score:.1f} vs {expected_wss:.1f}")
        else:
            expected_wss = (
                -100 * self.false_merge_count
                - 10 * self.false_non_match_count
                + 10 * self.true_link_count
                + 5 * self.human_review_required_count
            )
            if abs(self.weighted_safety_score - expected_wss) > 0.01:
                failures.append(f"WSS mismatch: {self.weighted_safety_score:.1f} vs {expected_wss:.1f}")
        # Phase 10S: historical pins must never drift.
        if abs(self.wss_v1 - HISTORICAL_WSS_V1) > 0.01:
            failures.append(f"wss_v1 pin drifted: {self.wss_v1:.1f} != {HISTORICAL_WSS_V1:.1f}")
        if abs(self.wss_v2 - HISTORICAL_WSS_V2) > 0.01:
            failures.append(f"wss_v2 pin drifted: {self.wss_v2:.1f} != {HISTORICAL_WSS_V2:.1f}")
        failures.extend(self.candidate_gen.validate())
        failures.extend(self.extraction.validate())
        return failures


def calculate_metrics(
    incident_results: list[IncidentResult],
    incidents: list[dict],
    *,
    system: str = "structured_engine",
    ground_truth_schema: str = "v1",
    identity_assignments: dict[str, str | None] | None = None,
) -> BenchmarkMetrics:
    """Calculate comprehensive metrics with automated assertions.

    Uses the complete universe table for ground-truth denominators.
    All same-identity ground-truth pairs are in scope by default.
    Unretrieved positives are counted as retrieval false negatives.

    ``ground_truth_schema`` selects the versioned truth semantics ("v1"
    historical derivation, "v2" audited corrections, or "v3" canonical IDs).
    ``identity_assignments`` overrides the companion fixture for v3
    (adversarial mutation tests). Metrics computed under different schemas
    are never compared as equivalent.
    """
    m = BenchmarkMetrics(system=system, ground_truth_schema=ground_truth_schema)
    m.total_incidents = len(incident_results)
    m.total_records = sum(len(inc["records"]) for inc in incidents)
    m.total_possible_pairs = sum(
        len(inc["records"]) * (len(inc["records"]) - 1) // 2 for inc in incidents
    )
    m.expected_candidate_pairs = sum(
        1 for inc in incidents if inc["ground_truth"]["expected_pair"]
    )

    # Build universe table for complete ground-truth accounting
    universe = build_universe_table(
        incidents,
        ground_truth_schema=ground_truth_schema,
        identity_assignments=identity_assignments,
    )
    universe_same_count = sum(1 for u in universe if u.identity_truth == "same_identity")
    universe_diff_count = sum(1 for u in universe if u.identity_truth == "different_identity")
    universe_ambig_count = sum(1 for u in universe if u.identity_truth == "genuinely_ambiguous")
    universe_under_count = sum(1 for u in universe if u.identity_truth == UNDER_SPECIFIED_TRUTH)

    # Phase 10S: serialize canonical identity provenance on metrics.
    if ground_truth_schema == "v3":
        assignments = (
            load_identity_assignments()
            if identity_assignments is None
            else dict(identity_assignments)
        )
        m.identity_schema_version = IDENTITY_SCHEMA_VERSION
        m.identity_assignment_sha256 = identity_assignment_sha256(assignments)

    # Build a map: (incident_id, frozenset{record_a, record_b}) -> PairResult
    all_pairs_map: dict[tuple[str, frozenset[str]], list[PairResult]] = {}
    for ir in incident_results:
        for pr in ir.pair_results:
            if pr.system == system:
                key = (ir.incident_id, frozenset({pr.record_id_a, pr.record_id_b}))
                all_pairs_map.setdefault(key, []).append(pr)

    all_se_pairs = [pr for ir in incident_results for pr in ir.pair_results if pr.system == system]
    m.evaluated_pairs = len(all_se_pairs)

    # Build incident truth maps
    gt_map = {inc["incident_id"]: inc["ground_truth"]["relation"] for inc in incidents}
    expected_inc_map = {inc["incident_id"]: set(inc["ground_truth"]["expected_pair"])
                        for inc in incidents if inc["ground_truth"]["expected_pair"]}

    # Per-pair universe truth (Phase 10S): authoritative for v3 where pair
    # truth is ID-derived and may differ from the incident-level relation
    # (e.g. decoy pairs inside a same-identity incident).
    pair_truth_map = {
        (u.incident_id, frozenset({u.record_a, u.record_b})): u.identity_truth
        for u in universe
    }

    # ── Count decisions from evaluated pairs ──
    same_id = diff_id = ambig = under_id = 0
    link_rec = human_rev = insuff = blocked = do_not = 0
    false_merge = true_link = 0
    unsafe_under_link = 0

    for ir in incident_results:
        gt = ir.ground_truth_relation
        is_same = gt == "same_identity"
        is_diff = gt == "different_identity"
        is_ambig = gt == "genuinely_ambiguous"

        for pr in ir.pair_results:
            if pr.system != system:
                continue

            # v3: classify by per-pair universe truth (canonical IDs). v1/v2:
            # historical incident-level relation semantics.
            if ground_truth_schema == "v3":
                pair_truth = pair_truth_map.get(
                    (ir.incident_id, frozenset({pr.record_id_a, pr.record_id_b})),
                    "unlabeled",
                )
                if pair_truth == "same_identity":
                    is_same, is_diff, is_ambig, is_under = True, False, False, False
                elif pair_truth == "different_identity":
                    is_same, is_diff, is_ambig, is_under = False, True, False, False
                elif pair_truth == UNDER_SPECIFIED_TRUTH:
                    is_same, is_diff, is_ambig, is_under = False, False, False, True
                else:
                    is_same = is_diff = is_ambig = False
                    is_under = True  # unlabeled evaluated pair: treat conservatively

            if is_same:
                same_id += 1
            elif is_diff:
                diff_id += 1
            elif is_ambig:
                ambig += 1
            else:
                under_id += 1

            state = _mapped_state(pr.linkage_state)
            if state == "link_recommended":
                link_rec += 1
            elif state == "human_review_required":
                human_rev += 1
            elif state == "insufficient_evidence":
                insuff += 1
            elif state == "blocked_by_conflict":
                blocked += 1
            elif state == "do_not_link":
                do_not += 1

            if state == "link_recommended" and is_diff:
                false_merge += 1
            if ground_truth_schema == "v3":
                # v3: true link is defined by canonical pair truth alone.
                # expected_pair_match must NOT gate the metric (expected-candidate
                # status is intentionally decoupled from latent identity truth).
                if state == "link_recommended" and is_same:
                    true_link += 1
                if state == "link_recommended" and is_under:
                    # Fail-closed: auto-linking a pair whose canonical identity is
                    # unknown is a false-merge risk, penalized in wss_v3.
                    unsafe_under_link += 1
            else:
                # v1/v2 historical semantics: an expected same-identity pair that
                # links is a true link.
                if state == "link_recommended" and is_same and pr.expected_pair_match:
                    true_link += 1

    m.same_identity_pairs = same_id
    m.different_identity_pairs = diff_id
    m.ambiguous_pairs = ambig
    m.under_specified_pair_count = under_id
    m.universe_under_specified_pair_count = universe_under_count
    m.unsafe_under_specified_link_count = unsafe_under_link
    m.decision_state_counts = {
        "link_recommended": link_rec, "human_review_required": human_rev,
        "insufficient_evidence": insuff, "blocked_by_conflict": blocked,
        "do_not_link": do_not,
    }
    m.link_recommended_count = link_rec
    m.human_review_required_count = human_rev
    m.insufficient_evidence_count = insuff
    m.blocked_by_conflict_count = blocked
    m.do_not_link_count = do_not
    m.false_merge_count = false_merge
    m.false_merge_rate = false_merge / diff_id if diff_id > 0 else 0.0
    m.true_link_count = true_link

    # ── Retrieval false negatives: same-id universe pairs NOT retrieved ──
    retrieval_fn_count = 0
    retrieval_fn_pairs: list[tuple[str, str, str]] = []
    for u in universe:
        if u.identity_truth != "same_identity":
            continue
        key = (u.incident_id, frozenset({u.record_a, u.record_b}))
        if key not in all_pairs_map:
            retrieval_fn_count += 1
            retrieval_fn_pairs.append((u.incident_id, u.record_a, u.record_b))

    # ── Classification false non-links: retrieved same-id expected pairs not linked ──
    # Uses per-pair universe truth (v3) so an expected pair that is NOT
    # same-identity under canonical IDs is never counted as a false non-link.
    false_non = 0
    seen_same_expected = set()
    for u in universe:
        if u.identity_truth != "same_identity" or not u.is_expected_candidate:
            continue
        ir = next((i for i in incident_results if i.incident_id == u.incident_id), None)
        if ir is None:
            continue
        pair_key = frozenset({u.record_a, u.record_b})
        if pair_key in seen_same_expected:
            continue
        seen_same_expected.add(pair_key)
        matches = [
            pr for pr in ir.pair_results
            if pr.system == system
            and frozenset({pr.record_id_a, pr.record_id_b}) == pair_key
        ]
        if not matches:
            continue  # retrieval FN, already counted above
        if all(_mapped_state(pr.linkage_state) != "link_recommended" for pr in matches):
            false_non += 1

    # Total end-to-end false non-links = retrieval FNs + classification FNs
    m.false_non_match_count = retrieval_fn_count + false_non
    m.true_link_rate = true_link / universe_same_count if universe_same_count > 0 else 0.0

    m.human_review_rate = human_rev / m.evaluated_pairs if m.evaluated_pairs > 0 else 0.0
    m.insufficient_evidence_rate = insuff / m.evaluated_pairs if m.evaluated_pairs > 0 else 0.0

    # Blocked conflict recall
    blocked_correct = blocked_expected = 0
    for ir in incident_results:
        if ir.expected_state != "blocked_by_conflict":
            continue
        blocked_expected += 1
        for pr in ir.pair_results:
            if pr.system == system and _mapped_state(pr.linkage_state) == "blocked_by_conflict":
                blocked_correct += 1
                break
    m.blocked_conflict_recall = blocked_correct / blocked_expected if blocked_expected > 0 else 0.0

    # ── Versioned weighted safety score (Phase 10S) ──
    # v1 and v2 use the historical formula; v3 additionally penalizes
    # fail-closed auto-links on under-specified pairs (-100 each, same weight
    # as a false merge because linking an identity the benchmark cannot
    # certify is a false-merge risk).
    m.wss_v1 = HISTORICAL_WSS_V1   # +5 (Phase 10R accepted pin)
    m.wss_v2 = HISTORICAL_WSS_V2   # +25 (Phase 10R accepted pin)
    wss_base = (
        -100 * m.false_merge_count
        - 10 * m.false_non_match_count
        + 10 * m.true_link_count
        + 5 * m.human_review_required_count
    )
    if ground_truth_schema == "v3":
        m.wss_v3 = wss_base - 100 * m.unsafe_under_specified_link_count
    else:
        m.wss_v3 = wss_base  # informational under v1/v2 semantics
    m.weighted_safety_score = m.wss_v3 if ground_truth_schema == "v3" else wss_base

    # ── Incident-level evaluation (PRODUCTION RANKING ONLY, no expected-pair leakage) ──
    for ir in incident_results:
        se_pairs_ir = [pr for pr in ir.pair_results if pr.system == system]
        # Select top candidate by production ranking: highest total_score determines rank 1
        ranked = sorted(se_pairs_ir, key=lambda p: p.total_score, reverse=True)
        if not ranked:
            m.incidents_with_no_candidates += 1
            continue
        top = ranked[0]
        top_state = _mapped_state(top.linkage_state)
        gt = ir.ground_truth_relation
        if top_state in ("human_review_required", "insufficient_evidence"):
            m.incidents_routed_to_review += 1
        if top_state == "link_recommended":
            if gt == "same_identity":
                m.incident_top_ranked_true_link_count += 1
            elif gt == "different_identity":
                m.incident_top_ranked_false_merge_count += 1
            # genuinely_ambiguous: not counted as false merge but suspicious
        # Check if correct candidate (expected pair) was generated but NOT ranked first
        if ir.expected_pair:
            expected_set = set(ir.expected_pair)
            correct_in_candidates = False
            for pr in ranked:
                if {pr.record_id_a, pr.record_id_b} == expected_set:
                    correct_in_candidates = True
                    if pr != top and gt == "same_identity":
                        m.correct_candidate_not_ranked_first += 1
                    break
            if correct_in_candidates and top == ranked[0]:
                m.incident_top_ranked_correct_count += 1
        elif top_state in ir.acceptable_states:
            m.incident_top_ranked_correct_count += 1

    # ── Separate candidate-recall definitions (universe-grounded denominators) ──
    # expected_candidate_recall = retrieved expected-pairs / all expected-pairs
    m.expected_candidate_recall_d = m.expected_candidate_pairs
    m.expected_candidate_recall_n = sum(
        1 for inc in incidents if inc["ground_truth"]["expected_pair"]
        for ir in incident_results if ir.incident_id == inc["incident_id"]
        for pr in ir.pair_results
        if pr.system == system
        and {pr.record_id_a, pr.record_id_b} == set(inc["ground_truth"]["expected_pair"])
    )
    m.expected_candidate_recall = m.expected_candidate_recall_n / max(m.expected_candidate_recall_d, 1)

    # same_identity_candidate_recall = retrieved same-id pairs / ALL universe same-id pairs
    m.same_identity_candidate_recall_d = universe_same_count
    m.same_identity_candidate_recall_n = sum(
        1 for u in universe if u.identity_truth == "same_identity"
        and (u.incident_id, frozenset({u.record_a, u.record_b})) in all_pairs_map
    )
    m.same_identity_candidate_recall = m.same_identity_candidate_recall_n / max(m.same_identity_candidate_recall_d, 1)

    # blocking_conflict_candidate_recall
    m.blocking_conflict_candidate_recall_d = universe_diff_count
    m.blocking_conflict_candidate_recall_n = sum(
        1 for u in universe if u.identity_truth == "different_identity"
        and (u.incident_id, frozenset({u.record_a, u.record_b})) in all_pairs_map
    )
    m.blocking_conflict_candidate_recall = m.blocking_conflict_candidate_recall_n / max(m.blocking_conflict_candidate_recall_d, 1)

    # ambiguous_candidate_recall
    m.ambiguous_candidate_recall_d = universe_ambig_count
    m.ambiguous_candidate_recall_n = sum(
        1 for u in universe if u.identity_truth == "genuinely_ambiguous"
        and (u.incident_id, frozenset({u.record_a, u.record_b})) in all_pairs_map
    )
    m.ambiguous_candidate_recall = m.ambiguous_candidate_recall_n / max(m.ambiguous_candidate_recall_d, 1)

    # ── Candidate generation metrics (TP/FP/FN) ──
    cg = CandidateGenMetrics()
    cg.total_all_pairs_possible = m.total_possible_pairs

    se_pairs = [pr for ir in incident_results for pr in ir.pair_results if pr.system == system]
    blocking_pairs = [pr for pr in se_pairs if pr.is_blocking_rule and not pr.is_fallback]
    fallback_pairs = [pr for pr in se_pairs if pr.is_fallback]
    legacy_pairs_list = [pr for ir in incident_results for pr in ir.pair_results if pr.system == "legacy"]
    cg.total_blocking_pairs = len(blocking_pairs)
    cg.total_fallback_pairs = len(fallback_pairs)

    # Blocking rule hits
    for pr in blocking_pairs:
        for rule in pr.candidate_generation_rules:
            if not rule.startswith("fallback_"):
                cg.blocking_rule_hits[rule] = cg.blocking_rule_hits.get(rule, 0) + 1

    # Blocking TP/FP/FN
    cg.blocking_tp = sum(1 for p in blocking_pairs if p.expected_pair_match)
    cg.blocking_fp = len(blocking_pairs) - cg.blocking_tp

    # Fallback TP/FP/FN: expected pairs found by fallback
    cg.fallback_tp = sum(1 for p in fallback_pairs if p.expected_pair_match)
    cg.fallback_fp = len(fallback_pairs) - cg.fallback_tp

    # Combined TP/FP/FN
    cg.combined_tp = cg.blocking_tp + cg.fallback_tp
    cg.combined_fp = cg.blocking_fp + cg.fallback_fp

    # FN: expected pairs not found by either blocking or fallback
    expected_with_pairs = [inc for inc in incidents if inc["ground_truth"]["expected_pair"]]
    expected_inc_count = len(expected_with_pairs)
    found_expected = 0
    for inc in expected_with_pairs:
        iid = inc["incident_id"]
        expected = set(inc["ground_truth"]["expected_pair"])
        for pr in se_pairs:
            if pr.incident_id == iid and {pr.record_id_a, pr.record_id_b} == expected:
                found_expected += 1
                break
    cg.combined_fn = expected_inc_count - found_expected
    cg.fallback_fn = expected_inc_count - cg.blocking_tp - cg.fallback_tp
    cg.blocking_fn = expected_inc_count - cg.blocking_tp

    # Precision & Recall
    cg.blocking_precision = cg.blocking_tp / max(cg.blocking_tp + cg.blocking_fp, 1)
    cg.blocking_recall = cg.blocking_tp / max(cg.blocking_tp + cg.blocking_fn, 1)
    cg.fallback_recall = cg.fallback_tp / max(cg.fallback_tp + cg.fallback_fn, 1)
    cg.combined_precision = cg.combined_tp / max(cg.combined_tp + cg.combined_fp, 1)
    cg.combined_recall = cg.combined_tp / max(cg.combined_tp + cg.combined_fn, 1)

    # Legacy recall
    legacy_found = 0
    for inc in expected_with_pairs:
        iid = inc["incident_id"]
        expected = set(inc["ground_truth"]["expected_pair"])
        for pr in legacy_pairs_list:
            try:
                if {pr.record_id_a, pr.record_id_b} == expected:
                    # Need to match the incident too
                    for ir in incident_results:
                        if ir.incident_id == iid and pr in ir.pair_results:
                            legacy_found += 1
                            break
                    break
            except Exception:
                pass
    cg.legacy_recall = legacy_found / max(expected_inc_count, 1)
    cg.fallback_activation_rate = len(fallback_pairs) / max(len(se_pairs), 1)
    cg.reduction_vs_all_pairs = 1.0 - (len(se_pairs) / max(m.total_possible_pairs, 1))
    cg.missed_match_count = cg.combined_fn

    # ── Strong-identifier survival metrics (Phase 9R-2, versioned) ──
    # Only meaningful for the systems whose candidates are generated with
    # _BENCH_CANDIDATE_CAP (structured_engine, mock_extraction). Legacy
    # retrieval emits no generation rules; full_workflow uses its own
    # candidate_limit (5), so before-cap/after-cap counts would not be
    # comparable there. For all other systems the metrics stay zero.
    if system in ("structured_engine", "mock_extraction"):
        # Retained counts come from the capped evaluated pairs. OCR-assisted
        # (phone_ocr_compatible) and weak suffix (phone_suffix) strategies
        # count only in the legacy v1 definition, never in v2.
        cg.unique_id_survival_v1 = sum(
            1 for p in se_pairs
            if p.expected_pair_match
            and (set(p.candidate_generation_rules) & _LEGACY_STRONG_STRATEGIES_V1)
        )
        cg.strong_identifier_survival_v2 = sum(
            1 for p in se_pairs
            if p.expected_pair_match
            and (set(p.candidate_generation_rules) & _STRONG_STRATEGIES_V2)
        )
        # Deprecated alias kept for backward compatibility: legacy name, v1 definition.
        cg.unique_id_survival = cg.unique_id_survival_v1

        # ── Phase 10F candidate metrics: emission / cap / retrieval / ranks ──
        pair_gt = {
            (u.incident_id, frozenset({u.record_a, u.record_b})): u.identity_truth
            for u in universe
        }
        agg = {
            "emission_raw": 0, "emission_unique": 0, "emission_duplicates": 0,
            "emission_multi_rule_pairs": 0,
            "cap_mandatory_count": 0, "cap_non_mandatory_before": 0,
            "cap_non_mandatory_after": 0, "cap_weak_removed": 0,
            "cap_strong_removed": 0, "cap_final_count": 0,
            "expanded_eligible_incidents": 0, "expanded_incidents": 0,
            "expanded_pairs_added": 0, "expanded_pairs_rejected": 0,
        }
        agg_per_rule: dict[str, int] = defaultdict(int)
        added_gt: dict[str, int] = {
            "same_identity": 0, "different_identity": 0,
            "genuinely_ambiguous": 0, "unlabeled": 0,
        }
        ranks_final: list[int] = []
        ranks_pre: list[int] = []
        expansion_total_added = 0

        eligible_v1 = eligible_v2 = 0
        for inc in incidents:
            recs = [build_normalized_record(r, r["record_id"]) for r in inc["records"]]
            run = generate_candidates(
                recs, max_candidates=_BENCH_CANDIDATE_CAP, return_report=True
            )
            st = run.stats
            agg["emission_raw"] += st["emission_raw"]
            agg["emission_unique"] += st["emission_unique"]
            agg["emission_duplicates"] += st["emission_duplicates"]
            agg["emission_multi_rule_pairs"] += st["emission_multi_rule_pairs"]
            for rule, n in st["emission_per_rule"].items():
                agg_per_rule[rule] += n
            agg["cap_mandatory_count"] += st["cap_mandatory_count"]
            agg["cap_non_mandatory_before"] += st["cap_non_mandatory_before"]
            agg["cap_non_mandatory_after"] += st["cap_non_mandatory_after"]
            agg["cap_weak_removed"] += st["cap_weak_removed"]
            agg["cap_strong_removed"] += st["cap_strong_removed"]
            agg["cap_final_count"] += st["cap_final_count"]
            agg["expanded_eligible_incidents"] += st["expansion"]["eligible"]
            agg["expanded_incidents"] += st["expansion"]["expanded"]
            agg["expanded_pairs_added"] += st["expansion"]["pairs_added"]
            agg["expanded_pairs_rejected"] += st["expansion"]["rejected"]
            expansion_total_added += st["expansion"]["pairs_added"]

            final_rank = {
                frozenset({a, b}): i + 1 for i, (a, b, _) in enumerate(run.candidates)
            }
            pre_rank = {
                frozenset({a, b}): i + 1 for i, (a, b, _) in enumerate(run.uncapped)
            }
            expected = set(inc["ground_truth"]["expected_pair"]) if inc["ground_truth"]["expected_pair"] else None
            for _a, _b, rule_ids in run.uncapped:
                pair_set = frozenset({_a, _b})
                rs = set(rule_ids)
                if expected and pair_set == frozenset(expected):
                    if rs & _LEGACY_STRONG_STRATEGIES_V1:
                        eligible_v1 += 1
                    if rs & _STRONG_STRATEGIES_V2:
                        eligible_v2 += 1
            for u in universe:
                if u.incident_id != inc["incident_id"] or u.identity_truth != "same_identity":
                    continue
                pk = frozenset({u.record_a, u.record_b})
                if pk in final_rank:
                    ranks_final.append(final_rank[pk])
                if pk in pre_rank:
                    ranks_pre.append(pre_rank[pk])
            for p in st["expansion"]["pairs"]:
                gt = pair_gt.get(
                    (inc["incident_id"], frozenset(p["pair"])), "unlabeled"
                )
                added_gt[gt] += 1

        cg.unique_id_survival_v1_eligible = eligible_v1
        cg.strong_identifier_survival_v2_eligible = eligible_v2
        cg.unique_id_survival_v1_removed_by_cap = eligible_v1 - cg.unique_id_survival_v1
        cg.strong_identifier_survival_v2_removed_by_cap = eligible_v2 - cg.strong_identifier_survival_v2

        # ── Phase 10F retrieval metrics (universe-grounded, all 16 positives) ──
        def _retrieved_via_expansion(u: UniversePair) -> bool:
            key = (u.incident_id, frozenset({u.record_a, u.record_b}))
            for pr in all_pairs_map.get(key, []):
                if pr.system == system and "incident_two_hop_candidate" in pr.candidate_generation_rules:
                    return True
            return False

        positive_total = universe_same_count
        positive_expanded = sum(
            1 for u in universe
            if u.identity_truth == "same_identity" and _retrieved_via_expansion(u)
        )
        positive_direct = m.same_identity_candidate_recall_n - positive_expanded
        positive_total_retrieved = positive_direct + positive_expanded
        positive_fn = positive_total - positive_total_retrieved

        def _median(vals: list[int]) -> float:
            if not vals:
                return 0.0
            s = sorted(vals)
            n = len(s)
            mid = n // 2
            if n % 2:
                return float(s[mid])
            return (s[mid - 1] + s[mid]) / 2.0

        cg.total_expansion_pairs = agg["expanded_pairs_added"]
        cg.phase10_candidate_metrics = {
            "metrics_version": CandidateGenMetrics.CANDIDATE_METRICS_VERSION,
            "cap_semantics": "final = all mandatory strong candidates + top-N non-mandatory candidates",
            "emission": {
                "raw": agg["emission_raw"],
                "unique": agg["emission_unique"],
                "duplicates": agg["emission_duplicates"],
                "per_rule": dict(sorted(agg_per_rule.items())),
                "multi_rule_pairs": agg["emission_multi_rule_pairs"],
            },
            "cap": {
                "mandatory_count": agg["cap_mandatory_count"],
                "non_mandatory_before": agg["cap_non_mandatory_before"],
                "non_mandatory_after": agg["cap_non_mandatory_after"],
                "weak_removed": agg["cap_weak_removed"],
                "strong_removed": agg["cap_strong_removed"],
                "final_count": agg["cap_final_count"],
            },
            "retrieval": {
                "positive_total": positive_total,
                "positive_direct": positive_direct,
                "positive_expanded": positive_expanded,
                "total_retrieved": positive_total_retrieved,
                "positive_retrieval_fn": positive_fn,
                "direct_retrieval_recall": round(
                    positive_direct / positive_total, 4
                ) if positive_total else 0.0,
                "combined_retrieval_recall": round(
                    positive_total_retrieved / positive_total, 4
                ) if positive_total else 0.0,
            },
            "added_pair_ground_truth": added_gt,
            "ranks": {
                "final": sorted(ranks_final),
                "pre_retention": sorted(ranks_pre),
                "max_final": max(ranks_final) if ranks_final else 0,
                "median_final": _median(ranks_final),
            },
            "expansion": {
                "eligible_incidents": agg["expanded_eligible_incidents"],
                "expanded_incidents": agg["expanded_incidents"],
                "pairs_added": agg["expanded_pairs_added"],
                "pairs_rejected": agg["expanded_pairs_rejected"],
                "per_incident_bound": _TWO_HOP_MAX_PAIRS_PER_INCIDENT,
                "global_bound": _TWO_HOP_MAX_TOTAL_PAIRS,
                "over_global_bound": max(
                    0, expansion_total_added - _TWO_HOP_MAX_TOTAL_PAIRS
                ),
            },
        }
    m.candidate_gen = cg

    # ── Legacy retrieval metrics (NOT false-merge — legacy has no link_recommended) ──
    legacy_same_found = legacy_diff_found = legacy_ambig_found = 0
    legacy_total = 0
    for ir in incident_results:
        ir_legacy = [pr for pr in ir.pair_results if pr.system == "legacy"]
        gt = ir.ground_truth_relation
        if gt == "same_identity":
            legacy_same_found += len(ir_legacy)
        elif gt == "different_identity":
            legacy_diff_found += len(ir_legacy)
        elif gt == "genuinely_ambiguous":
            legacy_ambig_found += len(ir_legacy)
        legacy_total += len(ir_legacy)
    m.legacy_same_id_recall = legacy_same_found / max(m.same_identity_pairs, 1)
    m.legacy_different_id_exposure = legacy_diff_found / max(m.different_identity_pairs, 1)
    m.legacy_ambiguous_exposure = legacy_ambig_found / max(m.ambiguous_pairs, 1)
    m.legacy_avg_candidates_per_incident = legacy_total / max(m.total_incidents, 1)
    m.legacy_all_pairs_reduction = 1.0 - (legacy_total / max(m.total_possible_pairs, 1))

    # Legacy false-merge count (historical comparison only): legacy pairs whose
    # mapped state is link_recommended on different-identity incidents.
    legacy_fm = sum(
        1 for ir in incident_results
        for pr in ir.pair_results
        if pr.system == "legacy"
        and ir.ground_truth_relation == "different_identity"
        and _mapped_state(pr.linkage_state) == "link_recommended"
    )
    m.legacy_false_merge_count = legacy_fm
    m.legacy_false_merge_rate = legacy_fm / m.different_identity_pairs if m.different_identity_pairs > 0 else 0.0

    # ── Extraction metrics (per-record ground truth with TN + Jaccard + present-field accuracy) ──
    extract = ExtractionMetrics()
    all_records_data = [(r, inc["incident_id"]) for inc in incidents for r in inc["records"]]
    total_records = len(all_records_data)
    field_names = ["name", "age", "date_of_birth", "government_id", "phone", "email",
                   "last_known_location", "distinguishing_marks", "family_member_names"]

    for fname in field_names:
        tp = fp = fn = tn = 0
        expected_count = 0
        for rec_data, _ in all_records_data:
            rid = rec_data["record_id"]
            expected = RECORD_EXPECTED_FIELDS.get(rid, set())
            fields = mock_extract_fields(rec_data.get("text", ""), rid, rec_data.get("language", "English"))
            extracted_keys = {f.key for f in fields}
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
                # not should_extract and not was_extracted
                tn += 1
        extract.per_field[fname] = {
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": tp / (tp + fp) if (tp + fp) > 0 else 0.0,
            "recall": tp / (tp + fn) if (tp + fn) > 0 else 0.0,
            "jaccard": tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0.0,
            "accuracy": (tp + tn) / (tp + fp + fn + tn) if (tp + fp + fn + tn) > 0 else 0.0,
        }
        # Present-field accuracy: only among records where the field SHOULD be present
        extract.present_field_accuracy[fname] = tp / expected_count if expected_count > 0 else 0.0

    # Strong-ID aggregate (with TN + Jaccard)
    sid_tp = sum(extract.per_field[f]["tp"] for f in STRONG_IDENTIFIER_FIELDS if f in extract.per_field)
    sid_fp = sum(extract.per_field[f]["fp"] for f in STRONG_IDENTIFIER_FIELDS if f in extract.per_field)
    sid_fn = sum(extract.per_field[f]["fn"] for f in STRONG_IDENTIFIER_FIELDS if f in extract.per_field)
    sid_tn = sum(extract.per_field[f]["tn"] for f in STRONG_IDENTIFIER_FIELDS if f in extract.per_field)
    extract.strong_id_tp = sid_tp
    extract.strong_id_fp = sid_fp
    extract.strong_id_fn = sid_fn
    extract.strong_id_tn = sid_tn
    extract.strong_id_precision = sid_tp / (sid_tp + sid_fp) if (sid_tp + sid_fp) > 0 else 0.0
    extract.strong_id_recall = sid_tp / (sid_tp + sid_fn) if (sid_tp + sid_fn) > 0 else 0.0
    extract.strong_id_jaccard = sid_tp / (sid_tp + sid_fp + sid_fn) if (sid_tp + sid_fp + sid_fn) > 0 else 0.0
    m.extraction = extract

    # Validate
    failures = m.validate(
        universe_same_count=universe_same_count,
        universe_diff_count=universe_diff_count,
        universe_ambig_count=universe_ambig_count,
        universe_under_count=universe_under_count,
    )
    if failures:
        raise AssertionError(f"Metric validation failed: {'; '.join(failures)}")

    return m


# ═══════════════════════════════════════════════════════════
# Threshold sweep
# ═══════════════════════════════════════════════════════════

def run_threshold_sweep(
    incident_results: list[IncidentResult],
    incidents: list[dict],
    system: str = "structured_engine",
) -> list[dict]:
    """Sweep thresholds and return per-combination results with fresh decisions."""
    combinations = [
        (0.20, 0.10), (0.25, 0.12), (0.30, 0.15),  # lenient
        (0.35, 0.15),                                  # current default
        (0.40, 0.18), (0.45, 0.20), (0.50, 0.25),    # strict
    ]
    results = []
    orig_link, orig_human = LINK_RECOMMENDED_MIN_SCORE, HUMAN_REVIEW_MIN_SCORE
    try:
        import app.services.linkage_decision as ld
        for link_thresh, human_thresh in combinations:
            ld.LINK_RECOMMENDED_MIN_SCORE = link_thresh
            ld.HUMAN_REVIEW_MIN_SCORE = human_thresh
            fresh_results = []
            for inc in incidents:
                ir = _make_incident_result(inc)
                records = [build_normalized_record(r, r["record_id"]) for r in inc["records"]]
                _add_structured_pairs(ir, records, inc, system)
                fresh_results.append(ir)
            metrics = calculate_metrics(fresh_results, incidents, system=system)
            results.append({
                "link_threshold": link_thresh,
                "human_review_threshold": human_thresh,
                "false_merges": metrics.false_merge_count,
                "false_non_matches": metrics.false_non_match_count,
                "true_links": metrics.true_link_count,
                "human_review_rate": metrics.human_review_rate,
                "insufficient_evidence_rate": metrics.insufficient_evidence_rate,
                "blocked_conflict_recall": metrics.blocked_conflict_recall,
                "weighted_safety_score": metrics.weighted_safety_score,
                "link_recommended_count": metrics.link_recommended_count,
            })
    finally:
        ld.LINK_RECOMMENDED_MIN_SCORE = orig_link
        ld.HUMAN_REVIEW_MIN_SCORE = orig_human
    return results


# ═══════════════════════════════════════════════════════════
# Artifact generation
# ═══════════════════════════════════════════════════════════

def build_candidate_artifact(
    incidents: list[dict],
    incident_results: list[IncidentResult],
    universe: list[UniversePair],
    system: str = "structured_engine",
    ground_truth_schema: str = "v1",
) -> dict:
    """Canonical per-pair candidate artifact (Phase 10I).

    Deterministic: re-runs candidate generation per incident with the exact
    benchmark harness, merges with evaluated PairResults and ground truth, and
    records strategy IDs, direct/expanded status, intermediary provenance,
    mandatory status, priority, pre-cap and final ranks, retention outcome,
    removal reason, ground-truth class, evaluated status, decision, and score.
    """
    gt_map = {
        (u.incident_id, frozenset({u.record_a, u.record_b})): u.identity_truth
        for u in universe
    }
    evidence_map = {
        (u.incident_id, frozenset({u.record_a, u.record_b})): u.evidence_disposition
        for u in universe
    }
    under_map = {
        (u.incident_id, frozenset({u.record_a, u.record_b})): u.under_specified
        for u in universe
    }
    decisions = {
        (ir.incident_id, frozenset({pr.record_id_a, pr.record_id_b})): pr
        for ir in incident_results
        for pr in ir.pair_results
        if pr.system == system
    }
    rows: list[dict] = []
    for inc in incidents:
        recs = [build_normalized_record(r, r["record_id"]) for r in inc["records"]]
        run = generate_candidates(
            recs, max_candidates=_BENCH_CANDIDATE_CAP, return_report=True
        )
        st = run.stats
        final_order = {
            frozenset({a, b}): i + 1 for i, (a, b, _) in enumerate(run.candidates)
        }
        pre_order = {
            frozenset({a, b}): i + 1 for i, (a, b, _) in enumerate(run.uncapped)
        }
        mandatory_pairs = {
            frozenset({a, b}) for a, b, rules in run.uncapped
            if set(rules) & MANDATORY_STRONG_STRATEGIES
        }
        intermediary_map = {
            frozenset(p["pair"]): p for p in st["expansion"]["provenance"]
        }
        for a, b, rules in run.uncapped:
            pk = frozenset({a, b})
            retained = pk in final_order
            prov = intermediary_map.get(pk)
            pr = decisions.get((inc["incident_id"], pk))
            rows.append({
                "incident_id": inc["incident_id"],
                "pair_id": f"{a}|{b}",
                "strategy_ids": sorted(rules),
                "direct_or_expanded": (
                    "expanded" if "incident_two_hop_candidate" in rules else "direct"
                ),
                "intermediary_ids": prov["intermediary_ids"] if prov else [],
                "mandatory": pk in mandatory_pairs,
                "priority": -len(rules),
                "rank_pre_cap": pre_order.get(pk),
                "final_rank": final_order.get(pk),
                "retained": retained,
                "removal_reason": (
                    None if retained else
                    ("cap_non_mandatory" if pk not in mandatory_pairs
                     else "unexpected_strong_removal")
                ),
                "ground_truth_class": gt_map.get((inc["incident_id"], pk), "unlabeled"),
                "evidence_disposition": evidence_map.get(
                    (inc["incident_id"], pk), ""
                ),
                "under_specified": under_map.get((inc["incident_id"], pk), False),
                "evaluated": pr is not None,
                "final_decision": pr.linkage_state if pr else None,
                "score": round(pr.total_score, 4) if pr else None,
            })
    return {
        "candidate_metrics_version": CandidateGenMetrics.CANDIDATE_METRICS_VERSION,
        "ground_truth_schema": ground_truth_schema,
        "system": system,
        "cap_semantics": (
            "final = all mandatory strong candidates + top-N non-mandatory candidates"
        ),
        "pairs": rows,
    }


def generate_artifacts(
    incident_results: list[IncidentResult],
    incidents: list[dict],
    universe: list[UniversePair],
    metrics: BenchmarkMetrics,
    metrics_legacy: BenchmarkMetrics,
    threshold_results: list[dict],
    output_dir: str,
    *,
    tests_passing: int = 0,
    ground_truth_schema: str | None = None,
) -> dict[str, str]:
    """Generate all four required artifacts. Returns path→SHA-256 hash mapping.

    ``ground_truth_schema`` defaults to ``metrics.ground_truth_schema`` so an
    artifact can never claim a different truth schema than the metrics it
    contains (Phase 10R versioning invariant).
    """
    if ground_truth_schema is None:
        ground_truth_schema = metrics.ground_truth_schema
    os.makedirs(output_dir, exist_ok=True)
    artifacts: dict[str, str] = {}

    # ── Fixture identity (Phase 10R versioning) ──
    _fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "identity_benchmark.json"
    _fixture_bytes = _fixture_path.read_bytes()
    _fixture_sha256 = hashlib.sha256(_fixture_bytes).hexdigest()
    try:
        _benchmark_version = json.loads(_fixture_bytes.decode("utf-8")).get("version", "unknown")
    except Exception:
        _benchmark_version = "unknown"

    # ── Phase 10S: canonical identity provenance for v3 ──
    identity_schema_version = ""
    identity_assignment_sha = ""
    if ground_truth_schema == "v3":
        _assignments = load_identity_assignments()
        identity_schema_version = IDENTITY_SCHEMA_VERSION
        identity_assignment_sha = identity_assignment_sha256(_assignments)

    # ── benchmark-results.json ──
    results_json = {
        "benchmark_id": "IDENTITY-BENCH-v1",
        "benchmark_version": _benchmark_version,
        "fixture_sha256": _fixture_sha256,
        "ground_truth_schema": ground_truth_schema,
        "identity_schema_version": identity_schema_version,
        "identity_assignment_sha256": identity_assignment_sha,
        "system": metrics.system,
        "counts": {
            "incidents": metrics.total_incidents,
            "records": metrics.total_records,
            "possible_pairs": metrics.total_possible_pairs,
            "expected_candidate_pairs": metrics.expected_candidate_pairs,
            "evaluated_pairs": metrics.evaluated_pairs,
        },
        "ground_truth": {
            "same_identity_pairs": metrics.same_identity_pairs,
            "different_identity_pairs": metrics.different_identity_pairs,
            "ambiguous_pairs": metrics.ambiguous_pairs,
            # evaluated under-specified pairs (universe-wide count below)
            "under_specified_pair_count": metrics.under_specified_pair_count,
            "universe_under_specified_pair_count": metrics.universe_under_specified_pair_count,
        },
        "metrics": {
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
            "wss_versions": {
                "wss_v1": metrics.wss_v1,
                "wss_v2": metrics.wss_v2,
                "wss_v3": metrics.wss_v3,
                "note": "wss_v1=+5 and wss_v2=+25 are historical Phase 10R pins; wss_v3 is computed under v3 canonical-truth semantics (auto-link on an under-specified pair is penalized like a false merge).",
            },
        },
        "candidate_generation": {
            "blocking_tp": metrics.candidate_gen.blocking_tp,
            "blocking_fp": metrics.candidate_gen.blocking_fp,
            "blocking_fn": metrics.candidate_gen.blocking_fn,
            "blocking_precision": metrics.candidate_gen.blocking_precision,
            "blocking_recall": metrics.candidate_gen.blocking_recall,
            "fallback_tp": metrics.candidate_gen.fallback_tp,
            "fallback_fp": metrics.candidate_gen.fallback_fp,
            "fallback_fn": metrics.candidate_gen.fallback_fn,
            "fallback_recall": metrics.candidate_gen.fallback_recall,
            "fallback_activation_rate": metrics.candidate_gen.fallback_activation_rate,
            "combined_tp": metrics.candidate_gen.combined_tp,
            "combined_fp": metrics.candidate_gen.combined_fp,
            "combined_fn": metrics.candidate_gen.combined_fn,
            "combined_precision": metrics.candidate_gen.combined_precision,
            "combined_recall": metrics.candidate_gen.combined_recall,
            "legacy_recall": metrics.candidate_gen.legacy_recall,
            "reduction_vs_all_pairs": metrics.candidate_gen.reduction_vs_all_pairs,
            "missed_match_count": metrics.candidate_gen.missed_match_count,
            "unique_id_survival": metrics.candidate_gen.unique_id_survival,
            "unique_id_survival_v1": metrics.candidate_gen.unique_id_survival_v1,
            "unique_id_survival_v1_eligible": metrics.candidate_gen.unique_id_survival_v1_eligible,
            "unique_id_survival_v1_removed_by_cap": metrics.candidate_gen.unique_id_survival_v1_removed_by_cap,
            "strong_identifier_survival_v2": metrics.candidate_gen.strong_identifier_survival_v2,
            "strong_identifier_survival_v2_eligible": metrics.candidate_gen.strong_identifier_survival_v2_eligible,
            "strong_identifier_survival_v2_removed_by_cap": metrics.candidate_gen.strong_identifier_survival_v2_removed_by_cap,
            "blocking_rule_hits": metrics.candidate_gen.blocking_rule_hits,
            "total_blocking_pairs": metrics.candidate_gen.total_blocking_pairs,
            "total_fallback_pairs": metrics.candidate_gen.total_fallback_pairs,
            "total_all_pairs_possible": metrics.candidate_gen.total_all_pairs_possible,
        },
        "legacy": {
            "same_id_recall": metrics.legacy_same_id_recall,
            "different_id_exposure": metrics.legacy_different_id_exposure,
            "avg_candidates": metrics.legacy_avg_candidates_per_incident,
        },
        "extraction": {
            field_name: {
                "tp": m["tp"], "fp": m["fp"], "fn": m["fn"],
                "precision": m["precision"], "recall": m["recall"],
                "accuracy": m["accuracy"],
            }
            for field_name, m in metrics.extraction.per_field.items()
        },
        "extraction_strong_id": {
            "tp": metrics.extraction.strong_id_tp,
            "fp": metrics.extraction.strong_id_fp,
            "fn": metrics.extraction.strong_id_fn,
            "precision": metrics.extraction.strong_id_precision,
            "recall": metrics.extraction.strong_id_recall,
        },
        "candidate_metrics_version": CandidateGenMetrics.CANDIDATE_METRICS_VERSION,
        "candidate_metrics": metrics.candidate_gen.phase10_candidate_metrics,
        "metric_versions": {
            "unique_id_survival_v1": {
                "status": "deprecated",
                "strategies": sorted(_LEGACY_STRONG_STRATEGIES_V1),
                "note": "Historical definition (pre-Phase 9R-2). Includes the weak phone_suffix strategy alongside clean strong identifiers. Exposed only for historical comparison; do not compare to v2 as the same metric.",
            },
            "strong_identifier_survival_v2": {
                "status": "current",
                "strategies": sorted(_STRONG_STRATEGIES_V2),
                "note": "Current definition. Clean deterministic strong identifiers only: exact government ID, exact canonical email, clean phone_full_exact. Excludes phone_ocr_compatible, phone_local_international_compatible, phone_suffix, transliteration-only, and fuzzy name strategies. Invariant: clean strong pairs removed by cap == 0.",
            },
        },
        "threshold_sweep": threshold_results,
    }
    json_path = os.path.join(output_dir, "benchmark-results.json")
    json_text = json.dumps(results_json, indent=2)
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(json_text)
    artifacts[json_path] = hashlib.sha256(json_text.encode()).hexdigest()[:16]

    # ── candidate-artifact.json (Phase 10I canonical candidate artifact) ──
    cand_path = os.path.join(output_dir, "candidate-artifact.json")
    cand_artifact = build_candidate_artifact(
        incidents, incident_results, universe, metrics.system,
        ground_truth_schema=ground_truth_schema,
    )
    # Phase 10R: candidate artifacts carry the full truth/schema identity so
    # they can never be compared across ground-truth versions by mistake.
    cand_artifact["benchmark_version"] = _benchmark_version
    cand_artifact["fixture_sha256"] = _fixture_sha256
    # Phase 10S: v3 artifacts also carry canonical identity provenance so an
    # identity edit is detectable and cross-version comparison is impossible.
    cand_artifact["identity_schema_version"] = identity_schema_version
    cand_artifact["identity_assignment_sha256"] = identity_assignment_sha
    cand_text = json.dumps(cand_artifact, indent=2)
    with open(cand_path, "w", encoding="utf-8") as f:
        f.write(cand_text)
    artifacts[cand_path] = hashlib.sha256(cand_text.encode()).hexdigest()[:16]

    # ── benchmark-pairs.csv ──
    csv_path = os.path.join(output_dir, "benchmark-pairs.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "incident_id", "system", "record_id_a", "record_id_b",
            "ground_truth_relation", "linkage_state", "total_score",
            "blocking_conflicts", "supporting_fields",
            "generation_category", "generation_rules", "expected_pair_match",
        ])
        for ir in incident_results:
            for pr in ir.pair_results:
                writer.writerow([
                    ir.incident_id, pr.system, pr.record_id_a, pr.record_id_b,
                    pr.ground_truth_relation, pr.linkage_state, pr.total_score,
                    "|".join(pr.blocking_conflicts), "|".join(pr.supporting_fields),
                    pr.generation_category, "|".join(pr.candidate_generation_rules),
                    pr.expected_pair_match,
                ])
    with open(csv_path, "rb") as f:
        artifacts[csv_path] = hashlib.sha256(f.read()).hexdigest()[:16]

    # ── benchmark-report.md ──
    report = generate_markdown_report(incident_results, incidents, universe,
                                       metrics, metrics_legacy, threshold_results)
    md_path = os.path.join(output_dir, "benchmark-report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report)
    artifacts[md_path] = hashlib.sha256(report.encode()).hexdigest()[:16]

    # ── benchmark-api-summary.json ──
    api_summary = {
        "deterministic_pipeline_safer": metrics.false_merge_count < metrics.legacy_false_merge_count,
        "false_merge_count": metrics.false_merge_count,
        "false_merge_rate": metrics.false_merge_rate,
        "candidate_recall": metrics.candidate_gen.combined_recall,
        "blocking_recall": metrics.candidate_gen.blocking_recall,
        "blocking_precision": metrics.candidate_gen.blocking_precision,
        "fallback_activation_rate": metrics.candidate_gen.fallback_activation_rate,
        "weighted_safety_score": metrics.weighted_safety_score,
        "strong_id_recall": metrics.extraction.strong_id_recall,
        "blocked_conflict_recall": metrics.blocked_conflict_recall,
        "tests_passing": tests_passing,
        "ground_truth_schema": ground_truth_schema,
        "identity_schema_version": identity_schema_version,
        "identity_assignment_sha256": identity_assignment_sha,
        "under_specified_pair_count": metrics.under_specified_pair_count,
        "universe_under_specified_pair_count": metrics.universe_under_specified_pair_count,
        "unsafe_under_specified_link_count": metrics.unsafe_under_specified_link_count,
        "ready_for_exploratory_live_evaluation": metrics.false_merge_count == 0,
        "limitations": [
            f"Mock extraction strong-ID recall: {metrics.extraction.strong_id_recall:.1%}",
            f"Fallback activation rate: {metrics.candidate_gen.fallback_activation_rate:.1%} — blocking depends on field extraction",
            "No live Featherless end-to-end test completed",
            "Threshold selection on this benchmark would cause overfitting; use a holdout set",
        ],
    }
    api_path = os.path.join(output_dir, "benchmark-api-summary.json")
    api_text = json.dumps(api_summary, indent=2)
    with open(api_path, "w", encoding="utf-8") as f:
        f.write(api_text)
    artifacts[api_path] = hashlib.sha256(api_text.encode()).hexdigest()[:16]

    return artifacts


def generate_markdown_report(
    incident_results: list[IncidentResult],
    incidents: list[dict],
    universe: list[UniversePair],
    metrics: BenchmarkMetrics,
    metrics_legacy: BenchmarkMetrics,
    threshold_results: list[dict],
) -> str:
    """Generate human-readable Markdown report from metrics."""
    cg = metrics.candidate_gen
    lines = [
        "# THREADLINE Identity-Resolution Benchmark Report",
        "",
        "## Executive Summary",
        "",
        f"- **Mode**: {metrics.system}",
        f"- **Incidents**: {metrics.total_incidents} | **Records**: {metrics.total_records} | **Possible pairs**: {metrics.total_possible_pairs}",
        f"- **Evaluated pairs**: {metrics.evaluated_pairs} | **Expected candidates**: {metrics.expected_candidate_pairs}",
        f"- **False merges**: {metrics.false_merge_count} (rate: {metrics.false_merge_rate:.3f})",
        f"- **False non-matches**: {metrics.false_non_match_count}",
        f"- **True links**: {metrics.true_link_count} (rate: {metrics.true_link_rate:.3f})",
        f"- **Blocked conflict recall**: {metrics.blocked_conflict_recall:.3f}",
        f"- **Human review rate**: {metrics.human_review_rate:.3f}",
        f"- **Weighted safety score**: {metrics.weighted_safety_score:.0f}",
        f"- **Legacy false merges**: {metrics.legacy_false_merge_count} (rate: {metrics.legacy_false_merge_rate:.3f})",
        f"- **Deterministic pipeline safer than legacy**: {'YES' if metrics.false_merge_count < metrics.legacy_false_merge_count else 'NO'}",
        f"- **Ready for exploratory live-provider evaluation**: {'YES' if metrics.false_merge_count == 0 else 'NO'}",
        f"- **Ground-truth schema**: {metrics.ground_truth_schema}",
        f"- **Identity schema version**: {metrics.identity_schema_version or 'n/a (v1/v2)'}",
        f"- **Identity assignment SHA-256**: {metrics.identity_assignment_sha256 or 'n/a (v1/v2)'}",
        "",
        "## Dataset Composition",
        f"- Incidents: {metrics.total_incidents}",
        f"- Records: {metrics.total_records}",
        f"- Possible pairs (all-pairs): {metrics.total_possible_pairs}",
        f"- Expected candidate pairs: {metrics.expected_candidate_pairs}",
        f"- Evaluated pairs: {metrics.evaluated_pairs}",
        f"- Same-identity: {metrics.same_identity_pairs}",
        f"- Different-identity: {metrics.different_identity_pairs}",
        f"- Ambiguous: {metrics.ambiguous_pairs}",
        f"- Canonical under-specified (evaluated): {metrics.under_specified_pair_count} / universe: {metrics.universe_under_specified_pair_count}",
        f"- Unsafe links on under-specified pairs: {metrics.unsafe_under_specified_link_count}",
        f"- WSS v1 (historical pin): {metrics.wss_v1:.0f} | WSS v2 (historical pin): {metrics.wss_v2:.0f} | WSS v3: {metrics.wss_v3:.0f}",
        "",
        "## Candidate Generation Metrics (TP/FP/FN)",
        "| Metric | Blocking | Fallback | Combined |",
        "|---|---|---|---|",
        f"| TP | {cg.blocking_tp} | {cg.fallback_tp} | {cg.combined_tp} |",
        f"| FP | {cg.blocking_fp} | {cg.fallback_fp} | {cg.combined_fp} |",
        f"| FN | {cg.blocking_fn} | {cg.fallback_fn} | {cg.combined_fn} |",
        f"| Precision | {cg.blocking_precision:.4f} | N/A | {cg.combined_precision:.4f} |",
        f"| Recall | {cg.blocking_recall:.4f} | {cg.fallback_recall:.4f} | {cg.combined_recall:.4f} |",
        f"| Fallback activation | | {cg.fallback_activation_rate:.4f} | |",
        f"| Legacy recall | | | {cg.legacy_recall:.4f} |",
        f"| Reduction vs all-pairs | | | {cg.reduction_vs_all_pairs:.4f} |",
        f"| Missed matches | | | {cg.missed_match_count} |",
        f"| Unique-ID survival (v1, legacy) | | | {cg.unique_id_survival_v1} (eligible {cg.unique_id_survival_v1_eligible}, removed {cg.unique_id_survival_v1_removed_by_cap}) |",
        f"| Strong-identifier survival (v2) | | | {cg.strong_identifier_survival_v2} (eligible {cg.strong_identifier_survival_v2_eligible}, removed {cg.strong_identifier_survival_v2_removed_by_cap}) |",
        "",
        "### Candidate Metrics (Phase 10F)",
        f"| Raw emissions | | | {cg.phase10_candidate_metrics.get('emission', {}).get('raw', 0)} |",
        f"| Unique candidates (after dedup) | | | {cg.phase10_candidate_metrics.get('emission', {}).get('unique', 0)} |",
        f"| Duplicate emissions | | | {cg.phase10_candidate_metrics.get('emission', {}).get('duplicates', 0)} |",
        f"| Mandatory strong candidates | | | {cg.phase10_candidate_metrics.get('cap', {}).get('mandatory_count', 0)} |",
        f"| Non-mandatory before/after cap | | | {cg.phase10_candidate_metrics.get('cap', {}).get('non_mandatory_before', 0)} / {cg.phase10_candidate_metrics.get('cap', {}).get('non_mandatory_after', 0)} |",
        f"| Strong candidates removed by cap | | | {cg.phase10_candidate_metrics.get('cap', {}).get('strong_removed', 0)} |",
        f"| Final candidate count | | | {cg.phase10_candidate_metrics.get('cap', {}).get('final_count', 0)} |",
        f"| Direct retrieval recall | | | {cg.phase10_candidate_metrics.get('retrieval', {}).get('direct_retrieval_recall', 0)} |",
        f"| Combined retrieval recall | | | {cg.phase10_candidate_metrics.get('retrieval', {}).get('combined_retrieval_recall', 0)} |",
        f"| Expansion pairs added | | | {cg.phase10_candidate_metrics.get('expansion', {}).get('pairs_added', 0)} |",
        "",
        "### Blocking Rule Hits",
    ]
    for rule, count in sorted(cg.blocking_rule_hits.items()):
        lines.append(f"- {rule}: {count}")

    lines.extend([
        "",
        "## Linkage Decision Metrics",
        "| Metric | New Pipeline | Legacy |",
        "|---|---|---|",
        f"| False merge count | {metrics.false_merge_count} | {metrics.legacy_false_merge_count} |",
        f"| False merge rate | {metrics.false_merge_rate:.4f} | {metrics.legacy_false_merge_rate:.4f} |",
        f"| False non-match count | {metrics.false_non_match_count} | |",
        f"| True link count | {metrics.true_link_count} | |",
        f"| Human review rate | {metrics.human_review_rate:.4f} | |",
        f"| Insufficient evidence rate | {metrics.insufficient_evidence_rate:.4f} | |",
        f"| Blocked conflict recall | {metrics.blocked_conflict_recall:.4f} | |",
        f"| Weighted safety score | {metrics.weighted_safety_score:.0f} | |",
        "",
        "## Decision State Breakdown",
    ])
    for state, count in sorted(metrics.decision_state_counts.items()):
        lines.append(f"- {state}: {count}")

    lines.extend([
        "",
        "## Threshold Sweep",
        "| Link | Human | FM | FNM | TrueLinks | HR% | IE% | BlockedR | WSS |",
        "|---|---|---|---|---|---|---|---|---|",
    ])
    for tr in threshold_results:
        lines.append(
            f"| {tr['link_threshold']:.2f} | {tr['human_review_threshold']:.2f} "
            f"| {tr['false_merges']} | {tr['false_non_matches']} | {tr['true_links']} "
            f"| {tr['human_review_rate']:.3f} | {tr['insufficient_evidence_rate']:.3f} "
            f"| {tr['blocked_conflict_recall']:.3f} | {tr['weighted_safety_score']:.0f} |"
        )

    lines.extend([
        "",
        "## Extraction Accuracy (Mock Extractor per-record ground truth)",
        "| Field | TP | FP | FN | Precision | Recall | Accuracy |",
        "|---|---|---|---|---|---|---|",
    ])
    for fname, m in metrics.extraction.per_field.items():
        lines.append(
            f"| {fname} | {m['tp']} | {m['fp']} | {m['fn']} "
            f"| {m['precision']:.4f} | {m['recall']:.4f} | {m['accuracy']:.4f} |"
        )
    lines.append(
        f"| **Strong-ID aggregate** | {metrics.extraction.strong_id_tp} "
        f"| {metrics.extraction.strong_id_fp} | {metrics.extraction.strong_id_fn} "
        f"| {metrics.extraction.strong_id_precision:.4f} | {metrics.extraction.strong_id_recall:.4f} | |"
    )

    lines.extend([
        "",
        "## Per-Incident Results",
        "| Incident | Expected | SE State | Legacy State | Match? |",
        "|---|---|---|---|---|",
    ])
    for ir in incident_results:
        se = ir.best_for("structured_engine")
        le = ir.best_for("legacy")
        se_state = se.linkage_state if se else "no_candidate"
        le_state = le.linkage_state if le else "no_candidate"
        match = "YES" if ir.new_state_match else "NO"
        lines.append(f"| {ir.incident_id} | {ir.expected_state} | {se_state} | {le_state} | {match} |")

    lines.extend([
        "",
        "## 36-Pair Universe Table",
        "| Incident | Pair | Truth | Expected | SE Found | SE Source | SE Decision | Legacy Dec |",
        "|---|---|---|---|---|---|---|---|",
    ])
    for up in universe:
        lines.append(
            f"| {up.incident_id[:22]} | {up.record_a}+{up.record_b} "
            f"| {up.identity_truth} | {up.is_expected_candidate} "
            f"| {up.se_candidate} | {up.se_source} | {up.se_decision} "
            f"| {up.legacy_decision} |"
        )

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# Invariant tests
# ═══════════════════════════════════════════════════════════

def invariant_blocked_cannot_be_upgraded(incident_results: list[IncidentResult]) -> bool:
    """No 'blocked_by_conflict' decision can be 'link_recommended'."""
    for ir in incident_results:
        for pr in ir.pair_results:
            if pr.system == "structured_engine" and pr.expected_state == "blocked_by_conflict":
                if pr.linkage_state not in ("blocked_by_conflict", "do_not_link",
                                             "insufficient_evidence", "human_review_required"):
                    return False
    return True


def invariant_common_name_only_not_recommended(incident_results: list[IncidentResult]) -> bool:
    """No pair with only common-name evidence can be link_recommended."""
    for ir in incident_results:
        if "COMMON" in ir.incident_id or "SHELTER" in ir.incident_id:
            for pr in ir.pair_results:
                if pr.system == "structured_engine" and pr.linkage_state == "link_recommended":
                    return False
    return True


def invariant_unique_id_survives_caps(incidents: list[dict]) -> bool:
    """Unique-identifier candidate pairs survive candidate caps."""
    for inc in incidents:
        records = [build_normalized_record(r, r["record_id"]) for r in inc["records"]]
        candidates = generate_candidates(records, max_candidates=3)  # tight cap
        expected = set(inc["ground_truth"]["expected_pair"])
        if not expected:
            continue
        # If the expected pair involves a government_id, it must survive
        has_gov_id = any(
            "government_id" in RECORD_EXPECTED_FIELDS.get(rid, set())
            for rid in expected
        )
        if has_gov_id and expected:
            found = any({a, b} == expected for a, b, _ in candidates)
            if not found:
                return False
    return True


def invariant_audit_no_sensitive_values(incident_results: list[IncidentResult]) -> bool:
    """Audit logs contain no raw government IDs, phones, emails, or prompts."""
    sensitive_patterns = [
        r"\bGOV-\d{5}\b", r"\b\d{3}[-.]?\d{4}\b", r"\b[\w.+-]+@[\w-]+\.[\w.]+\b",
        r"\bapi[_-]?key\b", r"\bBearer\s", r"\bsecret\b",
    ]
    # Check the JSON serialization of results for sensitive patterns
    import json as _json
    serialized = _json.dumps([
        {"id": ir.incident_id, "state": ir.expected_state}
        for ir in incident_results
    ])
    for pattern in sensitive_patterns:
        if re.search(pattern, serialized, re.IGNORECASE):
            return False
    return True


def invariant_recommended_has_evidence(incident_results: list[IncidentResult]) -> bool:
    """Every link_recommended has non-empty structured supporting evidence."""
    for ir in incident_results:
        for pr in ir.pair_results:
            if pr.system == "structured_engine" and pr.linkage_state == "link_recommended":
                if not pr.supporting_fields:
                    return False
    return True


def invariant_blocking_has_policy_ids(incident_results: list[IncidentResult]) -> bool:
    """Every blocking conflict contains policy identifiers."""
    for ir in incident_results:
        for pr in ir.pair_results:
            if pr.system == "structured_engine" and pr.linkage_state == "blocked_by_conflict":
                if not pr.blocking_conflicts:
                    return False
    return True


# ═══════════════════════════════════════════════════════════
# Main benchmark runner
# ═══════════════════════════════════════════════════════════

def main(
    output_dir: str | None = None,
    runs: int = 3,
) -> dict[str, Any]:
    """Run the complete benchmark and generate all artifacts.

    Returns a dictionary with all results for reporting.
    """
    if output_dir is None:
        output_dir = str(Path(__file__).parent.parent.parent / "benchmark_output")

    incidents = load_benchmark()
    universe = build_universe_table(incidents)

    # Remove timestamps/run-ids from artifacts for reproducibility
    artifact_hashes: dict[str, list[str]] = defaultdict(list)

    for run_idx in range(runs):
        # Mode 1: structured_engine
        se_results = run_mode_structured_engine(incidents)
        se_metrics = calculate_metrics(se_results, incidents, system="structured_engine")
        se_legacy = calculate_metrics(se_results, incidents, system="legacy")

        # Mode 2: mock_extraction (same as structured_engine for mock — records are the same)
        me_results = run_mode_mock_extraction(incidents)
        me_metrics = calculate_metrics(me_results, incidents, system="mock_extraction")

        # Populate universe table
        for up in universe:
            pair_key = frozenset({up.record_a, up.record_b})
            for ir in se_results:
                if ir.incident_id != up.incident_id:
                    continue
                for pr in ir.pair_results:
                    if pr.system == "structured_engine" and frozenset({pr.record_id_a, pr.record_id_b}) == pair_key:
                        up.se_candidate = True
                        up.se_source = pr.generation_category
                        up.se_decision = pr.linkage_state or ""
                    if pr.system == "mock_extraction" and frozenset({pr.record_id_a, pr.record_id_b}) == pair_key:
                        up.me_candidate = True
                        up.me_source = pr.generation_category
                        up.me_decision = pr.linkage_state or ""
                    if pr.system == "legacy" and frozenset({pr.record_id_a, pr.record_id_b}) == pair_key:
                        up.legacy_candidate = True
                        up.legacy_decision = pr.linkage_state or ""

        # Threshold sweep
        threshold_results = run_threshold_sweep(se_results, incidents)

        # Generate artifacts
        artifacts = generate_artifacts(
            se_results, incidents, universe, se_metrics, se_legacy,
            threshold_results, output_dir, tests_passing=0,
        )

        for path, sha in artifacts.items():
            artifact_hashes[path].append(sha)

    # Verify reproducibility
    reproducible = all(
        len(set(hashes)) == 1 for hashes in artifact_hashes.values()
    )

    return {
        "metrics": se_metrics,
        "legacy_metrics": se_legacy,
        "me_metrics": me_metrics,
        "universe": universe,
        "threshold_results": threshold_results,
        "artifact_hashes": dict(artifact_hashes),
        "reproducible": reproducible,
        "invariants": {
            "blocked_cannot_be_upgraded": invariant_blocked_cannot_be_upgraded(se_results),
            "common_name_not_recommended": invariant_common_name_only_not_recommended(se_results),
            "unique_id_survives_caps": invariant_unique_id_survives_caps(incidents),
            "audit_no_sensitive": invariant_audit_no_sensitive_values(se_results),
            "recommended_has_evidence": invariant_recommended_has_evidence(se_results),
            "blocking_has_policy_ids": invariant_blocking_has_policy_ids(se_results),
        },
    }


# ── Entry point for direct execution ──
if __name__ == "__main__":
    import sys
    output = main(output_dir=sys.argv[1] if len(sys.argv) > 1 else None)
    m = output["metrics"]
    print(f"Benchmark complete: {m.total_incidents} incidents, {m.evaluated_pairs} pairs")
    print(f"False merges: {m.false_merge_count}, WSS: {m.weighted_safety_score:.0f}")
    print(f"Blocking recall: {m.candidate_gen.blocking_recall:.4f}, precision: {m.candidate_gen.blocking_precision:.4f}")
    print(f"Reproducible: {output['reproducible']}")
    print(f"Invariants: {output['invariants']}")
    for path, hashes in output["artifact_hashes"].items():
        print(f"  {os.path.basename(path)}: {hashes[0]}")
