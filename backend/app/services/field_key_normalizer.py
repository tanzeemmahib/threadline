"""
Canonical field-key enum and deterministic alias-normalization policy.

SINGLE SOURCE OF TRUTH for all field keys used by:
- extraction schemas (ExtractedField.key)
- deterministic mock extraction
- live-provider extraction
- pairwise comparison
- evidence claims
- benchmark ground truth

Also provides fail-closed normalization: unknown keys that look like identifiers,
dates, phones, or family relations force human_review_required rather than silently
disappearing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal


# ═══════════════════════════════════════════════════════════
# Canonical field-key enum — single source of truth
# ═══════════════════════════════════════════════════════════

class CanonicalFieldKey(StrEnum):
    """Every supported field key. All extraction, comparison, and evidence modules
    MUST use these values. No duplicated key lists elsewhere."""
    name = "name"
    aliases = "aliases"
    age = "age"
    date_of_birth = "date_of_birth"
    government_id = "government_id"
    phone = "phone"
    email = "email"
    sex_gender = "sex_gender"
    language = "language"
    nationality = "nationality"
    physical_descriptors = "physical_descriptors"
    distinguishing_marks = "distinguishing_marks"
    clothing = "clothing"
    family_member_names = "family_member_names"
    home_address = "home_address"
    last_known_location = "last_known_location"
    shelter_location = "shelter_location"
    last_seen_time = "last_seen_time"
    timeline_event = "timeline_event"


# Canonical keys that constitute strong identifiers (for fail-closed routing)
STRONG_IDENTIFIER_CANONICAL_KEYS: frozenset[CanonicalFieldKey] = frozenset({
    CanonicalFieldKey.government_id,
    CanonicalFieldKey.phone,
    CanonicalFieldKey.email,
})

# Canonical keys that could represent sensitive personal data
SENSITIVE_CANONICAL_KEYS: frozenset[CanonicalFieldKey] = frozenset({
    CanonicalFieldKey.name,
    CanonicalFieldKey.date_of_birth,
    CanonicalFieldKey.government_id,
    CanonicalFieldKey.phone,
    CanonicalFieldKey.email,
    CanonicalFieldKey.home_address,
})

# Canonical keys that carry relationship/relational information
RELATIONSHIP_CANONICAL_KEYS: frozenset[CanonicalFieldKey] = frozenset({
    CanonicalFieldKey.family_member_names,
})


# ═══════════════════════════════════════════════════════════
# Alias-normalization policy (versioned)
# ═══════════════════════════════════════════════════════════

# Map of (lowercased, stripped) alias → canonical key.
# Aliases are case-insensitive. Whitespace is collapsed before lookup.
ALIAS_POLICY_VERSION = "1.0.0"

CANONICAL_ALIAS_MAP: dict[str, CanonicalFieldKey] = {
    # ── name ──
    "name": CanonicalFieldKey.name,
    "full_name": CanonicalFieldKey.name,
    "full name": CanonicalFieldKey.name,
    "person_name": CanonicalFieldKey.name,
    "person name": CanonicalFieldKey.name,
    "given_name": CanonicalFieldKey.name,
    "surname": CanonicalFieldKey.name,
    "family_name": CanonicalFieldKey.name,
    "first_name": CanonicalFieldKey.name,
    "last_name": CanonicalFieldKey.name,
    # ── aliases ──
    "aliases": CanonicalFieldKey.aliases,
    "alias": CanonicalFieldKey.aliases,
    "nickname": CanonicalFieldKey.aliases,
    "also_known_as": CanonicalFieldKey.aliases,
    # ── age ──
    "age": CanonicalFieldKey.age,
    "approximate_age": CanonicalFieldKey.age,
    "estimated_age": CanonicalFieldKey.age,
    "age_range": CanonicalFieldKey.age,
    # ── date_of_birth ──
    "date_of_birth": CanonicalFieldKey.date_of_birth,
    "dob": CanonicalFieldKey.date_of_birth,
    "birth_date": CanonicalFieldKey.date_of_birth,
    "birth date": CanonicalFieldKey.date_of_birth,
    "date of birth": CanonicalFieldKey.date_of_birth,
    "birthday": CanonicalFieldKey.date_of_birth,
    "born": CanonicalFieldKey.date_of_birth,
    # ── government_id ──
    "government_id": CanonicalFieldKey.government_id,
    "id": CanonicalFieldKey.government_id,
    "government id": CanonicalFieldKey.government_id,
    "gov_id": CanonicalFieldKey.government_id,
    "gov id": CanonicalFieldKey.government_id,
    "national_id": CanonicalFieldKey.government_id,
    "national id": CanonicalFieldKey.government_id,
    "aid_id": CanonicalFieldKey.government_id,
    "registration_number": CanonicalFieldKey.government_id,
    "registration number": CanonicalFieldKey.government_id,
    "identity_card": CanonicalFieldKey.government_id,
    "id_number": CanonicalFieldKey.government_id,
    "id number": CanonicalFieldKey.government_id,
    "passport": CanonicalFieldKey.government_id,
    # ── phone ──
    "phone": CanonicalFieldKey.phone,
    "telephone": CanonicalFieldKey.phone,
    "phone_number": CanonicalFieldKey.phone,
    "phone number": CanonicalFieldKey.phone,
    "mobile": CanonicalFieldKey.phone,
    "cell": CanonicalFieldKey.phone,
    "cellphone": CanonicalFieldKey.phone,
    "contact_phone": CanonicalFieldKey.phone,
    "contact number": CanonicalFieldKey.phone,
    "tel": CanonicalFieldKey.phone,
    # ── email ──
    "email": CanonicalFieldKey.email,
    "e-mail": CanonicalFieldKey.email,
    "e_mail": CanonicalFieldKey.email,
    "mail": CanonicalFieldKey.email,
    "email_address": CanonicalFieldKey.email,
    "email address": CanonicalFieldKey.email,
    "contact_email": CanonicalFieldKey.email,
    # ── sex_gender ──
    "sex": CanonicalFieldKey.sex_gender,
    "gender": CanonicalFieldKey.sex_gender,
    "sex_gender": CanonicalFieldKey.sex_gender,
    # ── language ──
    "language": CanonicalFieldKey.language,
    "languages": CanonicalFieldKey.language,
    "spoken_languages": CanonicalFieldKey.language,
    # ── nationality ──
    "nationality": CanonicalFieldKey.nationality,
    "citizenship": CanonicalFieldKey.nationality,
    # ── distinguishing_marks ──
    "distinguishing_marks": CanonicalFieldKey.distinguishing_marks,
    "distinctive_features": CanonicalFieldKey.distinguishing_marks,
    "distinctive features": CanonicalFieldKey.distinguishing_marks,
    "scars": CanonicalFieldKey.distinguishing_marks,
    "tattoos": CanonicalFieldKey.distinguishing_marks,
    "marks": CanonicalFieldKey.distinguishing_marks,
    "injury": CanonicalFieldKey.distinguishing_marks,
    "injuries": CanonicalFieldKey.distinguishing_marks,
    "medical_condition": CanonicalFieldKey.distinguishing_marks,
    # ── clothing ──
    "clothing": CanonicalFieldKey.clothing,
    "clothing_description": CanonicalFieldKey.clothing,
    "clothes": CanonicalFieldKey.clothing,
    "garment": CanonicalFieldKey.clothing,
    "wearing": CanonicalFieldKey.clothing,
    # ── family_member_names ──
    "family_member_names": CanonicalFieldKey.family_member_names,
    "family_member": CanonicalFieldKey.family_member_names,
    "parent_name": CanonicalFieldKey.family_member_names,
    "mother_name": CanonicalFieldKey.family_member_names,
    "father_name": CanonicalFieldKey.family_member_names,
    "sibling_names": CanonicalFieldKey.family_member_names,
    "relative_names": CanonicalFieldKey.family_member_names,
    "relatives": CanonicalFieldKey.family_member_names,
    # ── location keys ──
    "home_address": CanonicalFieldKey.home_address,
    "address": CanonicalFieldKey.home_address,
    "residence": CanonicalFieldKey.home_address,
    "home": CanonicalFieldKey.home_address,
    "last_known_location": CanonicalFieldKey.last_known_location,
    "last_seen_location": CanonicalFieldKey.last_known_location,
    "location": CanonicalFieldKey.last_known_location,
    "last seen": CanonicalFieldKey.last_known_location,
    "seen_at": CanonicalFieldKey.last_known_location,
    "shelter_location": CanonicalFieldKey.shelter_location,
    "shelter": CanonicalFieldKey.shelter_location,
    "hospital_location": CanonicalFieldKey.shelter_location,
    "camp_location": CanonicalFieldKey.shelter_location,
    "camp": CanonicalFieldKey.shelter_location,
    "hospital": CanonicalFieldKey.shelter_location,
    # ── temporal ──
    "last_seen_time": CanonicalFieldKey.last_seen_time,
    "timestamp": CanonicalFieldKey.last_seen_time,
    "datetime_last_seen": CanonicalFieldKey.last_seen_time,
    "time": CanonicalFieldKey.last_seen_time,
    "datetime": CanonicalFieldKey.last_seen_time,
}


# NOTE: The following raw keys are NOT canonical and are intentionally EXCLUDED
# from the alias map because they carry relationship semantics that must be preserved.
# They are checked by _is_relationship_raw_key() and routed appropriately.
_RELATIONSHIP_RAW_KEYS: frozenset[str] = frozenset({
    "mother", "father", "parent", "sibling", "brother", "sister",
    "son", "daughter", "child", "spouse", "husband", "wife",
    "uncle", "aunt", "cousin", "grandmother", "grandfather",
    "guardian", "caretaker",
})


def _is_relationship_raw_key(raw_key_lower: str) -> bool:
    """Return True if the raw key represents a family relationship role."""
    return raw_key_lower in _RELATIONSHIP_RAW_KEYS


# ═══════════════════════════════════════════════════════════
# Normalization API
# ═══════════════════════════════════════════════════════════

class NormalizationStatus(StrEnum):
    canonical = "canonical"                    # Key was already canonical
    normalized_by_alias = "normalized_by_alias"  # Key matched an alias entry
    unknown_retained = "unknown_retained"      # Unknown key, harmless, retained
    unknown_review_required = "unknown_review_required"  # Unknown key, potential identifier
    relationship_key = "relationship_key"      # Relationship-type key, mapped to family_member_names
    ambiguous_alias = "ambiguous_alias"        # Multiple canonical candidates, not mapped


@dataclass(frozen=True, slots=True)
class NormalizedFieldKey:
    """Result of normalizing a raw extraction key."""
    raw_key: str                          # Original key from extraction output
    canonical_key: CanonicalFieldKey | None  # Resolved canonical key, or None
    status: NormalizationStatus
    normalization_rule_id: str            # e.g., "alias:v1:id→government_id"
    reason_code: str | None = None        # For unknown/ambiguous keys
    relationship_type: str | None = None  # e.g., "mother", "father" if relationship key


def normalize_field_key(raw_key: str) -> NormalizedFieldKey:
    """Deterministically normalize a raw extraction key to a canonical key.

    Rules (in order):
    1. If raw_key is already a CanonicalFieldKey value → canonical, no change.
    2. If lowercased/trimmed alias matches → normalized_by_alias with rule ID.
    3. If lowercased raw key is a relationship term → mapped to family_member_names
       with relationship_type preserved.
    4. If unknown but looks like an identifier/date/phone/email → unknown_review_required.
    5. Otherwise → unknown_retained (harmless, excluded from scoring).
    """
    canonical_str = raw_key.strip()

    # Rule 1: Already canonical
    try:
        canonical = CanonicalFieldKey(canonical_str)
        return NormalizedFieldKey(
            raw_key=raw_key,
            canonical_key=canonical,
            status=NormalizationStatus.canonical,
            normalization_rule_id=f"canonical:v{ALIAS_POLICY_VERSION}:{canonical.value}",
        )
    except ValueError:
        pass

    # Rule 2: Alias lookup
    lookup = canonical_str.lower().strip()
    if lookup in CANONICAL_ALIAS_MAP:
        canonical = CANONICAL_ALIAS_MAP[lookup]
        return NormalizedFieldKey(
            raw_key=raw_key,
            canonical_key=canonical,
            status=NormalizationStatus.normalized_by_alias,
            normalization_rule_id=f"alias:v{ALIAS_POLICY_VERSION}:{lookup}→{canonical.value}",
        )

    # Rule 3: Relationship key
    if _is_relationship_raw_key(lookup):
        return NormalizedFieldKey(
            raw_key=raw_key,
            canonical_key=CanonicalFieldKey.family_member_names,
            status=NormalizationStatus.relationship_key,
            normalization_rule_id=f"relationship:v{ALIAS_POLICY_VERSION}:{lookup}→family_member_names",
            relationship_type=lookup,
        )

    # Rule 4: Unknown but potentially sensitive
    if _looks_like_identifier(lookup):
        return NormalizedFieldKey(
            raw_key=raw_key,
            canonical_key=None,
            status=NormalizationStatus.unknown_review_required,
            normalization_rule_id=f"unknown_sensitive:v{ALIAS_POLICY_VERSION}:{lookup}",
            reason_code="STRONG_IDENTIFIER_KEY_NOT_CANONICAL",
        )

    # Rule 5: Harmless unknown
    return NormalizedFieldKey(
        raw_key=raw_key,
        canonical_key=None,
        status=NormalizationStatus.unknown_retained,
        normalization_rule_id=f"unknown_retained:v{ALIAS_POLICY_VERSION}:{lookup}",
        reason_code="UNKNOWN_EXTRACTION_FIELD_KEY",
    )


def _looks_like_identifier(lookup: str) -> bool:
    """Heuristic: does a lowercased key look like it might contain an identifier?"""
    identifier_hints = {
        "id", "identifier", "passport", "license", "card", "number",
        "phone", "tel", "mobile", "cell", "contact",
        "email", "mail",
        "dob", "birth", "birthday", "date",
        "address", "location", "home",
    }
    return any(hint in lookup for hint in identifier_hints)


# ═══════════════════════════════════════════════════════════
# Canonical key list for extraction prompt (single source of truth)
# ═══════════════════════════════════════════════════════════

CANONICAL_KEY_DEFINITIONS: dict[CanonicalFieldKey, str] = {
    CanonicalFieldKey.name: "Full name as recorded in source (e.g., 'Youssef Al Hassan')",
    CanonicalFieldKey.aliases: "Alternative names or spelling variants (e.g., 'Yusuf Hasan')",
    CanonicalFieldKey.age: "Age in years: exact number, range, or approximate (e.g., '14', '12-16', '~45')",
    CanonicalFieldKey.date_of_birth: "Date of birth in ISO format when known (e.g., '2003-04-15', '2003')",
    CanonicalFieldKey.government_id: "Government/aid/registration identifier (e.g., 'GOV-12345')",
    CanonicalFieldKey.phone: "Phone number, digits only when possible (e.g., '5551234')",
    CanonicalFieldKey.email: "Email address, lowercased (e.g., 'person@example.com')",
    CanonicalFieldKey.sex_gender: "Sex or gender marker, exactly as recorded",
    CanonicalFieldKey.language: "Languages spoken, comma-separated (e.g., 'Arabic, French')",
    CanonicalFieldKey.nationality: "Nationality or citizenship, exactly as recorded",
    CanonicalFieldKey.physical_descriptors: "Height, build, hair color, eye color",
    CanonicalFieldKey.distinguishing_marks: "Scars, tattoos, marks, injuries, or distinctive features",
    CanonicalFieldKey.clothing: "Clothing description (e.g., 'navy hooded coat')",
    CanonicalFieldKey.family_member_names: "Names of family members mentioned (mother, father, sibling)",
    CanonicalFieldKey.home_address: "Home address or residence",
    CanonicalFieldKey.last_known_location: "Last known location or place last seen",
    CanonicalFieldKey.shelter_location: "Shelter, hospital, or camp location",
    CanonicalFieldKey.last_seen_time: "Date and time last seen (e.g., '2026-04-18 16:30')",
    CanonicalFieldKey.timeline_event: "Relevant timeline event with time and description",
}

# Prohibited key names that the LLM must NOT use
PROHIBITED_KEY_NAMES: list[str] = [
    "id", "DOB", "birth_date", "birth date", "government id",
    "gov_id", "cell", "mobile", "telephone", "e-mail",
    "address", "location", "time", "timestamp", "datetime",
    "mother", "father", "parent", "sibling",
    "injury", "scars", "marks",
]


def format_canonical_keys_for_prompt() -> str:
    """Generate a prompt block describing all canonical field keys."""
    lines = [
        "CANONICAL FIELD KEYS — use EXACTLY these keys:",
        "",
    ]
    for key in CanonicalFieldKey:
        definition = CANONICAL_KEY_DEFINITIONS.get(key, "")
        lines.append(f"  {key.value}: {definition}")
    lines.extend([
        "",
        "PROHIBITED KEY NAMES — do NOT use these:",
        f"  {', '.join(PROHIBITED_KEY_NAMES)}",
        "",
        "Use ONLY the exact canonical keys listed above. No abbreviations, no variations.",
        "If a piece of evidence does not fit any canonical key, omit it.",
    ])
    return "\n".join(lines)
