"""
Name normalization and transliteration-aware comparison forms.

Uses NameRepresentation from name_representation.py for deterministic,
transliteration-aware name handling. The raw extracted value is never
mutated.

Humanitarian safety principle: transliteration candidates are comparison
aids, not equivalence claims.
"""

from __future__ import annotations

from app.schemas.models import ExtractedField
from app.services.name_representation import (
    NameRepresentation,
    NameScript,
    represent_name,
    compare_names,
    NameComparisonResult,
    NameComparisonChannel,
)


def normalize_name(value: str) -> str:
    """Normalize a name for rapid comparison.

    Returns the normalized Latin transliteration form suitable for
    RapidFuzz comparison. This is a convenience wrapper around
    represent_name() for backward compatibility with existing code.

    For full provenance-aware comparison, use compare_names() directly
    with NameRepresentation objects.
    """
    rep = represent_name(value)
    return rep.normalized_latin_transliteration or value.lower()


def name_variants(value: str) -> list[str]:
    """Generate comparison-form variants of a name.

    Returns [original, normalized_latin, compact_form] without
    mutating the original value. For full representation including
    script and transliteration metadata, use represent_name().
    """
    rep = represent_name(value)
    variants = [value]
    if rep.normalized_latin_transliteration:
        variants.append(rep.normalized_latin_transliteration)
    compact = rep.normalized_latin_transliteration.replace(" ", "") if rep.normalized_latin_transliteration else ""
    if compact and compact not in variants:
        variants.append(compact)
    return list(dict.fromkeys(variants))


def normalize_name_fields(fields: list[ExtractedField]) -> list[str]:
    """Normalize all name fields in a record.

    For each field with key='name', sets field.normalized_value and
    returns all variant forms. The raw field.value is never modified.
    """
    names: list[str] = []
    for field in fields:
        if field.key == "name" and isinstance(field.value, str):
            rep = represent_name(field.value)
            field.normalized_value = rep.normalized_latin_transliteration or field.value
            names.extend(name_variants(field.value))
    return list(dict.fromkeys(names))


def represent_record_names(
    fields: list[ExtractedField],
    record_id: str = "",
) -> list[NameRepresentation]:
    """Build NameRepresentation objects for every name field in a record.

    Returns one NameRepresentation per name field, with full script
    detection, transliteration, and tokenization metadata.
    """
    reps: list[NameRepresentation] = []
    for field in fields:
        if field.key == "name" and isinstance(field.value, str):
            rep = represent_name(field.value, record_id=record_id)
            reps.append(rep)
    return reps


def compare_name_strings(
    left: str,
    right: str,
    fuzzy_threshold: float = 72.0,
) -> NameComparisonResult:
    """Convenience: compare two raw name strings using full representation.

    Returns a NameComparisonResult with channel, reason_code, and
    provenance metadata.
    """
    left_rep = represent_name(left)
    right_rep = represent_name(right)
    return compare_names(left_rep, right_rep, fuzzy_threshold=fuzzy_threshold)
