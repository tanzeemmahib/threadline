"""
Candidate generation with bounded recall using multiple blocking strategies.

Humanitarian safety principle: candidate generation is a recall step, not a decision.
Missing one field must not eliminate all candidates. Pathological pair explosions
are capped. Every candidate pair tracks which blocking rule produced it.

Phase 10 processing order (deterministic):
  1. Run every enabled blocking strategy and record every raw emission.
  2. Attach all releasing strategy IDs.
  3. Deduplicate by canonical unordered pair ID.
  4. Optionally run a bounded, incident-local, depth-1 second pass
     (``incident_two_hop_candidate``) — candidate-only, no evidence transfer.
  5. Mark mandatory clean strong-identifier candidates.
  6. Calculate deterministic priority (-#rules, record IDs).
  7. Retain ALL mandatory candidates.
  8. Apply the configured cap ONLY to non-mandatory candidates.
  9. Record removed candidates and reasons.
  10. Emit stable deterministic ordering.

Invariant: ``clean_strong_identifier_pairs_removed_by_cap == 0`` is enforced
structurally — mandatory candidates are never subject to the cap.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from app.schemas.models import NormalizedRecord
from app.services.name_representation import _consonant_skeleton
from app.services.normalization import normalize_name

# ─────────────────────────────────────────────────────────────
# Strategy classification (Phase 9R-2 / Phase 10)
# ─────────────────────────────────────────────────────────────

# Clean deterministic strong identifiers. Pairs released by any of these are
# MANDATORY: they always survive candidate caps.
MANDATORY_STRONG_STRATEGIES = frozenset({
    "government_id", "email_exact", "phone_full_exact",
})

# Rules strong enough to qualify a two-hop edge as "meaningful nontrivial".
# Edges that fire ONLY weak strategies (phone_suffix, phone_ocr_compatible),
# only generic name+location, or only a transliteration skeleton cannot seed
# expansion.
_TWO_HOP_MEANINGFUL_RULES = frozenset({
    "government_id", "email_exact", "phone_full_exact",
    "phone_local_international_compatible",
    "name_phonetic_plus_age",          # name + exact 5-year age bucket
    "family_member_plus_location",     # structured relationship + location
})

# Second-pass bounds (explicit, configurable, depth exactly one).
# The per-incident pair cap is ENFORCED inside _second_pass. The aggregate
# total is bounded by (incidents x per-incident cap); the benchmark reports
# the measured aggregate as `over_global_bound` for monitoring rather than
# silently dropping pairs after the fact (per-incident processing is the
# operative production bound).
_TWO_HOP_MAX_INCIDENT_RECORDS = 20
_TWO_HOP_MAX_MEANINGFUL_EDGES = 60
_TWO_HOP_MAX_PAIRS_PER_INCIDENT = 100
_TWO_HOP_MAX_TOTAL_PAIRS = 500


# ─────────────────────────────────────────────────────────────
# Blocking key generators
# ─────────────────────────────────────────────────────────────

def _normalize_phone_suffix(value: str, suffix_len: int = 7) -> str | None:
    """Extract last N digits of a phone number using shared phone parser."""
    from app.services.phone_parser import parse_phone_with_ocr
    parsed = parse_phone_with_ocr(value)
    digits = parsed.normalized_digits
    if len(digits) >= suffix_len:
        return digits[-suffix_len:]
    return None


def _phone_value(record: NormalizedRecord) -> str:
    """First phone field value on the record, or empty string."""
    return _field_value(record, ("phone", "phone_number", "contact_phone")) or ""


# Minimum digits for full-number phone blocking (a "complete" normalized phone)
_PHONE_FULL_MIN_DIGITS = 9
# Minimum national-number digits for local/international compatible blocking
_PHONE_NATIONAL_MIN_DIGITS = 7


def _phone_full_key(record: NormalizedRecord) -> str | None:
    """Full normalized phone representation (Phase 9R-2: phone_full_exact).

    CLEAN-ONLY. This key uses the core ``parse_phone`` parser, which performs
    no alphabetic OCR substitution. OCR-repaired values therefore never emit
    a ``full:`` key and can never produce ``phone_full_exact`` (they are
    handled by the separate ``phone_ocr_compatible`` strategy).

    Explicit international numbers use their complete international digit
    sequence; local numbers use their full normalized digits. Formatting,
    Unicode digit, and +/00 variants all collapse to the same key.
    """
    from app.services.phone_parser import parse_phone
    parsed = parse_phone(_phone_value(record))
    if not parsed.is_valid:
        return None
    digits = parsed.international_digits if parsed.explicit_international else parsed.normalized_digits
    if len(digits) >= _PHONE_FULL_MIN_DIGITS:
        return f"full:{digits}"
    return None


def _phone_local_intl_key(record: NormalizedRecord) -> str | None:
    """Conservative local/international compatible key (phone_local_international_compatible).

    CLEAN-ONLY (Phase 9R-2): uses the core ``parse_phone`` parser so OCR-
    repaired values never feed this rule either; OCR values route to
    ``phone_ocr_compatible``.

    An explicit international number emits its recognized national number; a
    local number emits its full normalized digits. Equal keys pair one side
    with the other. Explicit numbers with an unrecognized calling code emit
    nothing here (full-digit/suffix rules still apply).
    """
    from app.services.phone_parser import parse_phone
    parsed = parse_phone(_phone_value(record))
    if not parsed.is_valid:
        return None
    if parsed.explicit_international:
        if parsed.country_code and len(parsed.national_number) >= _PHONE_NATIONAL_MIN_DIGITS:
            return f"compat:{parsed.national_number}"
        return None
    if len(parsed.normalized_digits) >= _PHONE_NATIONAL_MIN_DIGITS:
        return f"compat:{parsed.normalized_digits}"
    return None


def _phone_intl_pair_ok(
    record_a: NormalizedRecord,
    record_b: NormalizedRecord,
    parse_fn,
) -> bool:
    """Pair-level guard shared by phone blocking rules: never pair two explicit
    international numbers whose complete digit sequences differ (a
    country-code conflict). Such pairs are left to the comparison layer, which
    reports them as conflicts.
    """
    pa = parse_fn(_phone_value(record_a))
    pb = parse_fn(_phone_value(record_b))
    if pa.explicit_international and pb.explicit_international:
        return pa.international_digits == pb.international_digits
    return True


def _phone_compat_pair_ok(record_a: NormalizedRecord, record_b: NormalizedRecord) -> bool:
    """Clean-only compatible-rule guard (Phase 9R-2)."""
    from app.services.phone_parser import parse_phone
    return _phone_intl_pair_ok(record_a, record_b, parse_phone)


def _phone_ocr_key(record: NormalizedRecord) -> str | None:
    """OCR-assisted full phone key (Phase 9R-2: phone_ocr_compatible).

    Emits a key ONLY when the conservative OCR repair stage actually repaired
    the value (``has_ocr_repair``). OCR-derived representations are never
    strong identifiers: they can never emit ``phone_full_exact`` and never
    count toward strong-identifier survival metrics.
    """
    from app.services.phone_parser import parse_phone_with_ocr
    parsed = parse_phone_with_ocr(_phone_value(record))
    if not parsed.has_ocr_repair:
        return None
    if not parsed.is_valid:
        return None
    digits = parsed.international_digits if parsed.explicit_international else parsed.normalized_digits
    if len(digits) >= _PHONE_FULL_MIN_DIGITS:
        return f"ocr:{digits}"
    return None


def _phone_ocr_pair_ok(record_a: NormalizedRecord, record_b: NormalizedRecord) -> bool:
    """OCR-compatible blocking must never pair two explicit international
    numbers whose complete (repaired) digit sequences differ.
    """
    from app.services.phone_parser import parse_phone_with_ocr
    return _phone_intl_pair_ok(record_a, record_b, parse_phone_with_ocr)


def _normalize_email_domain(value: str) -> str | None:
    """Extract lowercased email domain for loose blocking."""
    from app.services.email_normalizer import normalize_valid_email

    normalized = normalize_valid_email(value)
    return normalized.rsplit("@", 1)[1] if normalized else None


def _email_exact_key(record: NormalizedRecord) -> str | None:
    """Return a complete normalized email or no blocking key."""
    from app.services.email_normalizer import normalize_valid_email

    value = _field_value(record, ("email", "email_address", "contact_email"))
    return normalize_valid_email(value) if value else None


def _phonetic_key(name: str) -> str | None:
    """Simple phonetic-like key: first 3 consonants of the normalized name.

    This is a lightweight replacement for full Soundex/Metaphone. If the
    project later adds a phonetic library, replace this implementation.
    """
    norm = normalize_name(name)
    consonants = re.sub(r"[aeiou]", "", norm.lower())
    # Remove whitespace-equivalent and duplicates
    consonants = re.sub(r"[^a-z]", "", consonants)
    # Return first 3 unique consonants
    seen: set[str] = set()
    result = ""
    for c in consonants:
        if c not in seen:
            seen.add(c)
            result += c
        if len(result) >= 3:
            break
    return result if len(result) >= 2 else None


def _age_bucket(age_str: str | None) -> str | None:
    """Bucket age into 5-year windows for loose blocking."""
    if age_str is None:
        return None
    match = re.search(r"\b(\d{1,3})\b", str(age_str))
    if not match:
        return None
    age = int(match.group(1))
    bucket_start = (age // 5) * 5
    return f"{bucket_start}-{bucket_start + 4}"


# ─────────────────────────────────────────────────────────────
# Blocking rules
# ─────────────────────────────────────────────────────────────

BLOCKING_RULES: list[dict] = [
    {
        "rule_id": "phone_full_exact",
        "description": "Exact full normalized phone (formatting/Unicode/+/00 variants) — strong identifier",
        "key_fn": _phone_full_key,
    },
    {
        "rule_id": "phone_local_international_compatible",
        "description": "Explicit international national number == complete local number (clean only) — not strong",
        "key_fn": _phone_local_intl_key,
        "pair_ok": _phone_compat_pair_ok,
    },
    {
        "rule_id": "phone_ocr_compatible",
        "description": "OCR-assisted full phone match (repair recorded) — compatible strength only, never strong, never mandatory",
        "key_fn": _phone_ocr_key,
        "pair_ok": _phone_ocr_pair_ok,
    },
    {
        "rule_id": "phone_suffix",
        "description": "Weak phone suffix (last 7 digits) fallback; accepts clean or OCR-repaired values at weak strength only",
        "key_fn": lambda r: _normalize_phone_suffix(_phone_value(r)),
    },
    {
        "rule_id": "email_exact",
        "description": "Normalized full email address",
        "key_fn": _email_exact_key,
    },
    {
        "rule_id": "government_id",
        "description": "Government/aid identifier",
        "key_fn": lambda r: _field_value(
            r, ("government_id", "national_id", "aid_id", "registration_number")
        ),
    },
    {
        "rule_id": "name_phonetic_plus_age",
        "description": "Phonetic name key + age bucket",
        "key_fn": lambda r: (
            f"{_phonetic_key(_field_value(r, ('name',)) or '')}|{_age_bucket(_field_value(r, ('age',)) or '')}"
            if _phonetic_key(_field_value(r, ("name",)) or "")
            and _age_bucket(_field_value(r, ("age",)) or "")
            else None
        ),
    },
    {
        "rule_id": "name_plus_location",
        "description": "Normalized name first token + location",
        "key_fn": lambda r: (
            f"{((_field_value(r, ('name',)) or '').split()[0].lower() if (_field_value(r, ('name',)) or '') else '')}|"
            f"{(_field_value(r, ('last_known_location', 'location', 'last_seen_location')) or '').lower()}"
            if (_field_value(r, ("name",)))
            and (_field_value(r, ("last_known_location", "location", "last_seen_location")))
            else None
        ),
    },
    {
        "rule_id": "family_member_plus_location",
        "description": "Family member name first token + location",
        "key_fn": lambda r: (
            f"{((_field_value(r, ('family_member_names', 'parent_name', 'mother_name', 'father_name')) or '').split()[0].lower() if (_field_value(r, ('family_member_names', 'parent_name', 'mother_name', 'father_name')) or '') else '')}|"
            f"{(_field_value(r, ('last_known_location', 'location')) or '').lower()}"
            if (_field_value(r, ("family_member_names", "parent_name", "mother_name", "father_name")))
            and (_field_value(r, ("last_known_location", "location")))
            else None
        ),
    },
    {
        "rule_id": "name_transliteration_skeleton",
        "description": "Consonant skeleton of name (first 5 chars) — enables cross-script Arabic/Latin blocking",
        "key_fn": lambda r: (
            _consonant_skeleton(_field_value(r, ("name",)) or "")[:5]
            if _field_value(r, ("name",)) and len(
                _consonant_skeleton(_field_value(r, ("name",)) or "")
            ) >= 3
            else None
        ),
    },
]


def _field_value(record: NormalizedRecord, extraction_keys: tuple[str, ...]) -> str | None:
    """Find the first matching field value."""
    for field in record.fields:
        if field.key in extraction_keys and field.value is not None:
            return str(field.value)
    return None


# ─────────────────────────────────────────────────────────────
# Bounded incident-local second pass (Phase 10E)
# ─────────────────────────────────────────────────────────────

def _second_pass(
    records: list[NormalizedRecord],
    seen_pairs: dict[tuple[str, str], set[str]],
) -> dict:
    """Depth-1, incident-local, candidate-only expansion.

    When A–B and B–C are both directly retrieved by MEANINGFUL rules, a new
    candidate A–C may be emitted under ``incident_two_hop_candidate``. The
    pair is then evaluated by the ordinary pairwise workflow using ONLY A and
    C evidence — the intermediary is retrieval provenance, never identity
    evidence, and no score or field is transferred.

    Bounds (explicit): max incident records, max meaningful edges, max pairs
    per incident, depth exactly one (no recursive closure).
    """
    expansion: dict = {
        "eligible": 0,
        "expanded": 0,
        "pairs_added": 0,
        "rejected": 0,
        "pairs": [],       # [{pair, intermediary_ids, depth}]
        "provenance": [],  # [{pair, intermediary_ids, depth, edges}]
    }
    if len(records) > _TWO_HOP_MAX_INCIDENT_RECORDS:
        # No pairs attempted: rejected counts unique pairs refused by the
        # per-incident bound, so an early return contributes 0.
        return expansion
    expansion["eligible"] = 1

    meaningful = {
        pair: rs for pair, rs in seen_pairs.items()
        if rs & _TWO_HOP_MEANINGFUL_RULES
    }
    if not (2 <= len(meaningful) <= _TWO_HOP_MAX_MEANINGFUL_EDGES):
        return expansion

    adj: dict[str, set[str]] = defaultdict(set)
    for (a, b) in meaningful:
        adj[a].add(b)
        adj[b].add(a)

    added: list[tuple[str, str]] = []
    added_set: set[tuple[str, str]] = set()
    rejected_set: set[tuple[str, str]] = set()
    for a in sorted(adj):
        for b in sorted(adj[a]):
            for c in sorted(adj[b]):
                if c == a:
                    continue
                pair = (min(a, c), max(a, c))
                if pair in seen_pairs or pair in added_set:
                    continue
                if len(added) >= _TWO_HOP_MAX_PAIRS_PER_INCIDENT:
                    if pair not in rejected_set:
                        rejected_set.add(pair)
                        expansion["rejected"] += 1
                    continue
                added.append(pair)
                added_set.add(pair)

    expansion["pairs_added"] = len(added)
    expansion["expanded"] = 1 if added else 0

    for (a, c) in added:
        intermediaries = sorted(b for b in adj[a] if c in adj[b])
        # Every supporting edge is recorded (a–b and b–c for each intermediary).
        edge_pairs = []
        for b in intermediaries:
                edge_pairs.append(((min(a, b), max(a, b)), b))
                edge_pairs.append(((min(b, c), max(b, c)), b))
        provenance = {
            "pair": [a, c],
            "intermediary_ids": intermediaries,
            "depth": 1,
            "edges": [
                {
                    "pair": list(ep),
                    "intermediary": b,
                    "rules": sorted(meaningful[ep]),
                }
                for ep, b in edge_pairs
            ],
        }
        seen_pairs.setdefault((a, c), set()).add("incident_two_hop_candidate")
        expansion["pairs"].append({
            "pair": [a, c],
            "intermediary_ids": intermediaries,
            "depth": 1,
        })
        expansion["provenance"].append(provenance)
    return expansion


# ─────────────────────────────────────────────────────────────
# Candidate generation
# ─────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class CandidateRun:
    """Deterministic candidate-generation report (Phase 10).

    - ``candidates``: final list after mandatory retention + cap.
    - ``uncapped``: full pre-cap list (post second pass), for survival metrics.
    - ``stats``: emission / cap / expansion accounting.
    """
    candidates: list[tuple[str, str, list[str]]]
    uncapped: list[tuple[str, str, list[str]]]
    stats: dict


def generate_candidates(
    records: list[NormalizedRecord],
    max_candidates: int = 50,
    *,
    rules: list[dict] | None = None,
    return_report: bool = False,
    enable_two_hop: bool = True,
) -> list[tuple[str, str, list[str]]] | CandidateRun:
    """Generate candidate record pairs using multiple independent blocking strategies.

    Phase 10 processing order (see module docstring): emit all raw pairs,
    attach strategy IDs, deduplicate, optional bounded second pass, mark
    mandatory clean-strong pairs, deterministic priority, retain all mandatory
    pairs, cap only non-mandatory pairs, record removals, stable ordering.

    ``max_candidates`` semantics: the cap applies ONLY to non-mandatory
    candidates. Final candidates = all mandatory strong candidates + top-N
    non-mandatory candidates. The nominal cap may therefore be exceeded by the
    mandatory count; this is intentional — strong candidates are never dropped
    to preserve an arbitrary total.

    Args:
        records: Normalized records to generate candidates from.
        max_candidates: Cap on NON-MANDATORY candidate pairs returned.
        rules: Blocking rules to use (defaults to BLOCKING_RULES).
        return_report: When True, returns a CandidateRun (candidates, uncapped,
            stats) instead of a plain list.
        enable_two_hop: When True, run the bounded incident-local second pass.

    Returns:
        List of (record_id_a, record_id_b, rule_ids) sorted by number of
        blocking rules that produced the pair (descending), then by record IDs.
        When ``return_report`` is True, a CandidateRun.
    """
    if rules is None:
        rules = BLOCKING_RULES

    record_by_id = {r.record_id: r for r in records}
    seen_pairs: dict[tuple[str, str], set[str]] = defaultdict(set)
    raw_emissions = 0
    per_rule: dict[str, int] = defaultdict(int)

    # ── Step 1-3: emit all raw pairs, attach rule IDs, deduplicate ──
    for rule in rules:
        index: dict[str, list[str]] = defaultdict(list)
        for record in records:
            key = rule["key_fn"](record)
            if key is not None:
                index[key].append(record.record_id)

        pair_ok = rule.get("pair_ok")
        for _key, record_ids in index.items():
            if len(record_ids) < 2:
                continue
            record_ids.sort()
            for i in range(len(record_ids)):
                for j in range(i + 1, len(record_ids)):
                    a, b = record_ids[i], record_ids[j]
                    if a > b:
                        a, b = b, a
                    if pair_ok is not None and not pair_ok(record_by_id[a], record_by_id[b]):
                        continue
                    raw_emissions += 1
                    per_rule[rule["rule_id"]] += 1
                    seen_pairs[(a, b)].add(rule["rule_id"])

    # Fallback: if no blocking produced results, fall back to name-first-token
    # then all-pairs (strict dedup, bounded).
    if not seen_pairs and len(records) > 1:
        name_index: dict[str, list[str]] = defaultdict(list)
        for record in records:
            name_val = _field_value(record, ("name",))
            if name_val:
                first_token = name_val.split()[0].lower()
                name_index[first_token].append(record.record_id)

        for _key, rids in name_index.items():
            if len(rids) < 2:
                continue
            rids.sort()
            for i in range(len(rids)):
                for j in range(i + 1, len(rids)):
                    a, b = rids[i], rids[j]
                    if a > b:
                        a, b = b, a
                    raw_emissions += 1
                    per_rule["fallback_name_token"] += 1
                    seen_pairs[(a, b)].add("fallback_name_token")

        if not seen_pairs and len(records) <= 8:
            for i in range(len(records)):
                for j in range(i + 1, len(records)):
                    a, b = records[i].record_id, records[j].record_id
                    if a > b:
                        a, b = b, a
                    raw_emissions += 1
                    per_rule["fallback_all_pairs"] += 1
                    seen_pairs[(a, b)].add("fallback_all_pairs")

    # ── Step 4: bounded incident-local second pass (candidate-only) ──
    expansion = _second_pass(records, seen_pairs) if enable_two_hop else {
        "eligible": 0, "expanded": 0, "pairs_added": 0, "rejected": 0,
        "pairs": [], "provenance": [],
    }

    # ── Steps 5-9: mandatory retention, priority, cap, removals ──
    mandatory = {
        pair: rs for pair, rs in seen_pairs.items()
        if rs & MANDATORY_STRONG_STRATEGIES
    }
    non_mandatory = {
        pair: rs for pair, rs in seen_pairs.items() if pair not in mandatory
    }

    def _sort_key(item):
        (a, b), rs = item
        return (-len(rs), a, b)

    all_sorted = sorted(seen_pairs.items(), key=_sort_key)
    capped_non_mandatory = sorted(non_mandatory.items(), key=_sort_key)[:max_candidates]

    final_set: dict[tuple[str, str], set[str]] = dict(mandatory)
    final_set.update(capped_non_mandatory)
    final_sorted = sorted(final_set.items(), key=_sort_key)

    def _as_tuples(items):
        return [(a, b, sorted(rule_ids)) for (a, b), rule_ids in items]

    candidates = _as_tuples(final_sorted)
    uncapped = _as_tuples(all_sorted)

    stats = {
        "emission_raw": raw_emissions,
        "emission_unique": len(seen_pairs),
        "emission_duplicates": raw_emissions - len(seen_pairs),
        "emission_per_rule": dict(per_rule),
        "emission_multi_rule_pairs": sum(1 for rs in seen_pairs.values() if len(rs) >= 2),
        "cap_mandatory_count": len(mandatory),
        "cap_non_mandatory_before": len(non_mandatory),
        "cap_non_mandatory_after": len(capped_non_mandatory),
        "cap_weak_removed": len(non_mandatory) - len(capped_non_mandatory),
        "cap_strong_removed": 0,  # structural invariant
        "cap_final_count": len(final_sorted),
        "removed_reasons": {
            "cap_non_mandatory": len(non_mandatory) - len(capped_non_mandatory),
        },
        "expansion": expansion,
        "candidate_metrics_version": "1.0",
    }

    if return_report:
        return CandidateRun(candidates=candidates, uncapped=uncapped, stats=stats)
    return candidates


def candidate_reduction_ratio(
    records: list[NormalizedRecord], candidates: list[tuple[str, str, list[str]]]
) -> float:
    """Ratio of generated candidates to all possible pairs.

    Returns 1.0 if candidates == all possible pairs (no reduction).
    Returns 0.0 if no candidates (pathological, only with 0 or 1 records).
    """
    n = len(records)
    total_possible = n * (n - 1) // 2
    if total_possible == 0:
        return 1.0
    return round(len(candidates) / total_possible, 4)
