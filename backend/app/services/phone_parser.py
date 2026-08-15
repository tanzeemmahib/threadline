"""
Shared deterministic international phone parsing for THREADLINE.

Used by both production extraction and benchmark mock extraction.
No network calls. No LLM. No silent country-code assumptions.

Humanitarian safety principle: raw phone evidence is never mutated.
Normalized representations are derived, traceable, and auditable.

Phase 9R design invariants
--------------------------
1. An explicitly international number NEVER silently loses its international
   status because its calling code is absent from a lookup table.
   ``explicit_international == True`` holds for every explicit ``+`` or valid
   leading ``00`` representation regardless of country-code recognition.
2. Explicit-number equality compares the complete international digit
   sequence; it never depends on a partial country-code table, and it never
   falls back to a shared suffix when the full sequences differ.
3. No automatic regional assumption exists. A country code is only ever read
   from the value itself. Local numbers remain region-ambiguous.
4. Alphabetic OCR substitution (``l``->``1``, ``O``->``0``) is NOT performed by
   the core parser. It lives in an explicitly invoked repair stage
   (``ocr_repair_phone`` / ``parse_phone_with_ocr``) that records every repair
   operation and is never applied to labels, names, extensions, or narrative.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from enum import StrEnum

from app.services.unicode_normalizer import (
    normalize_digits_only,
    remove_directional_controls,
    normalize_arabic_punctuation,
)

PARSER_VERSION = "2.1.0"  # 2.1.0: parse_phone fails closed on alphabetic chars (no silent letter-drop)


# ═══════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════

class PhonePrefix(StrEnum):
    """Explicit international prefix type found in raw value."""
    plus = "plus"           # "+961..."
    double_zero = "double_zero"  # "00961..."
    none = "none"           # No explicit prefix


class PhoneComparisonOutcome(StrEnum):
    """Deterministic phone comparison result categories (Phase 9R)."""
    exact_match = "exact_match"                         # Clean full digits identical
    intl_prefix_equivalent = "intl_prefix_equivalent"   # +X == 00X, full digits match
    compatible_local_intl = "compatible_local_intl"      # explicit national == complete local number
    ocr_assisted_compatible = "ocr_assisted_compatible"  # full digits match only after conservative OCR repair
    weak_suffix_overlap = "weak_suffix_overlap"          # Only last 7+ digits match (weak)
    conflict = "conflict"                                # Full comparable numbers differ
    insufficient = "insufficient"                        # Too short, malformed, ambiguous


# ═══════════════════════════════════════════════════════════
# Extension markers
# ═══════════════════════════════════════════════════════════

_EXTENSION_PATTERN = re.compile(
    r"""(?ix)
    (?:\s+|^)
    (?P<marker>ext\.?|extension|poste|x)\s*
    (?P<digits>\d{1,6})
    \s*$
    """
)


# ═══════════════════════════════════════════════════════════
# Country calling codes (ITU-T E.164) — recognition only.
#
# This table is used ONLY to give explicit international numbers
# additional structure (country_code / national_number). Equality
# between two explicit international numbers compares their complete
# digit sequences and does NOT depend on this table. An unknown
# explicit calling code keeps explicit_international == True and is
# compared by its full international digits.
# ═══════════════════════════════════════════════════════════

_COUNTRY_CODES: frozenset[str] = frozenset({
    # 1-digit
    "1", "7",
    # 2-digit
    "20", "27", "30", "31", "32", "33", "34", "36", "39",
    "40", "41", "43", "44", "45", "46", "47", "48", "49",
    "51", "52", "53", "54", "55", "56", "57", "58",
    "60", "61", "62", "63", "64", "65", "66",
    "81", "82", "84", "86",
    "90", "91", "92", "93", "94", "95", "98",
    # 3-digit
    "211", "212", "213", "216", "218",
    "220", "221", "222", "223", "224", "225", "226", "227", "228", "229",
    "230", "231", "232", "233", "234", "235", "236", "237", "238", "239",
    "240", "241", "242", "243", "244", "245", "246", "247", "248", "249",
    "250", "251", "252", "253", "254", "255", "256", "257", "258", "260",
    "261", "262", "263", "264", "265", "266", "267", "268", "269",
    "290", "291", "297", "298", "299",
    "350", "351", "352", "353", "354", "355", "356", "357", "358", "359",
    "370", "371", "372", "373", "374", "375", "376", "377", "378", "380",
    "381", "382", "383", "385", "386", "387", "389",
    "420", "421", "423",
    "500", "501", "502", "503", "504", "505", "506", "507", "508", "509",
    "590", "591", "592", "593", "594", "595", "596", "597", "598", "599",
    "670", "672", "673", "674", "675", "676", "677", "678", "679",
    "680", "681", "682", "683", "685", "686", "687", "688", "689",
    "690", "691", "692",
    "850", "852", "853", "855", "856",
    "880", "886",
    "960", "961", "962", "963", "964", "965", "966", "967", "968",
    "970", "971", "972", "973", "974", "975", "976", "977",
    "992", "993", "994", "995", "996", "998",
})

_MAX_COUNTRY_CODE_LEN = 3

# Minimum digits required after a leading "00" before it is interpreted as an
# international prefix. A short local number that merely begins with "00"
# (e.g. "00123") must not be silently reinterpreted as "+1 23".
_MIN_INTERNATIONAL_AFTER_00 = 6


def _try_extract_country_code(digits: str, prefix: PhonePrefix) -> tuple[str, str]:
    """Separate a recognized calling code from an explicit international number.

    Only operates when an explicit international prefix (+ or 00) is present.
    Returns (country_code, national_number). When the calling code cannot be
    safely recognized, returns ("", "") — the caller keeps the full digit
    sequence as ``international_digits`` and never downgrades the number to a
    local national number.
    """
    if prefix == PhonePrefix.none:
        return "", ""
    if not digits:
        return "", ""

    # Longest match first (handles +1 vs +18x, +212 vs +21, etc.)
    for length in range(_MAX_COUNTRY_CODE_LEN, 0, -1):
        if len(digits) > length:
            candidate = digits[:length]
            if candidate in _COUNTRY_CODES:
                return candidate, digits[length:]
    return "", ""


# ═══════════════════════════════════════════════════════════
# Parsed phone representation
# ═══════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class ParsedPhone:
    """Deterministic parsed phone representation.

    Raw evidence is preserved verbatim. Normalized fields are
    derived representations used for comparison and blocking.
    """
    # ── Raw evidence (never mutated) ──
    raw_value: str
    original_digit_systems: list[str] = field(default_factory=list)

    # ── Normalized derived fields ──
    normalized_digits: str = ""            # ASCII digits only, no +, no formatting
    explicit_prefix: PhonePrefix = PhonePrefix.none
    explicit_prefix_digits: str = ""       # e.g. "1" for +1, "961" for +961; "" if unrecognized
    country_code: str = ""                 # Only when safely parsed from explicit prefix
    national_number: str = ""              # Digits after recognized country code
    extension: str = ""                    # Extension digits, if any
    has_plus: bool = False                 # Raw had a leading "+"
    has_double_zero: bool = False          # Raw had a leading "00"

    # ── OCR repair provenance (Phase 9R) ──
    ocr_repairs: list[dict] = field(default_factory=list)  # [{char, position, replacement, token}]

    # ── Metadata ──
    is_valid: bool = True                  # Has enough digits for comparison
    is_complete: bool = False              # Explicit prefix + sufficient national digits
    warnings: list[str] = field(default_factory=list)
    normalization_steps: list[str] = field(default_factory=list)
    version: str = PARSER_VERSION

    # ── Phase 9R invariants ──
    @property
    def explicit_international(self) -> bool:
        """True for every explicit ``+`` or valid leading ``00`` representation.

        This must remain True regardless of whether the calling code is
        recognized by the country-code table.
        """
        return self.explicit_prefix != PhonePrefix.none

    @property
    def international_digits(self) -> str:
        """Complete international digit sequence (prefix stripped).

        For explicit numbers this is the authoritative equality key.
        For local numbers this is empty.
        """
        return self.normalized_digits if self.explicit_international else ""

    @property
    def country_code_recognized(self) -> bool:
        """Whether the calling code was successfully separated."""
        return bool(self.country_code)

    @property
    def has_ocr_repair(self) -> bool:
        """Whether any conservative OCR letter->digit repair was applied."""
        return bool(self.ocr_repairs)

    @property
    def complete_digits(self) -> str:
        """Full comparable digit string (country_code + national_number)."""
        if self.country_code and self.national_number:
            return self.country_code + self.national_number
        return self.normalized_digits

    @property
    def min_comparable_length(self) -> int:
        """Minimum length for safe comparison."""
        return 7  # Last 7 digits minimum for suffix matching


# ═══════════════════════════════════════════════════════════
# Conservative OCR repair stage (Phase 9R)
# ═══════════════════════════════════════════════════════════

# OCR-confusable letters and their digit readings. Applied ONLY inside
# phone-like tokens (see ocr_repair_phone) — never to labels, names,
# extensions, or narrative text.
_OCR_LETTER_DIGITS: dict[str, str] = {"l": "1", "L": "1", "O": "0"}

# Phone punctuation used by the OCR guard: ASCII separators plus the Arabic
# comma (U+060C) and Arabic semicolon (U+061B).
_PHONE_PUNCT = set("+-()./،؛-")


@dataclass(frozen=True, slots=True)
class OcrPhoneRepair:
    """Result of the conservative OCR repair stage."""
    original: str
    repaired: str
    operations: list[dict]          # [{char, position, replacement, token}]
    confidence: float               # 1.0 when any repair applied; else 0.0
    ambiguous: bool
    warnings: list[str] = field(default_factory=list)


def ocr_repair_phone(raw: str) -> OcrPhoneRepair:
    """Conservatively repair OCR letter->digit artifacts in phone-like tokens.

    A letter is repaired only when ALL of the following hold:
    * the letter is one of the known OCR-confusable letters (l/L/O);
    * it appears inside a token overwhelmingly composed of digits and
      phone punctuation (at least 4 digits, no other letters);
    * a neighbouring character (before or after) is a digit or phone
      punctuation, establishing a digit position;
    * the repair produces a plausible phone token.

    Letters in labels, names, extensions, and surrounding narrative are
    never repaired. The unrepaired representation is preserved verbatim.
    """
    warnings: list[str] = []
    operations: list[dict] = []
    repaired_tokens: list[str] = []

    for token in raw.split():
        digits = sum(1 for ch in token if ch.isdigit())
        punct = sum(1 for ch in token if ch in _PHONE_PUNCT)
        letters = [ch for ch in token if ch.isalpha()]
        suspicious = [ch for ch in letters if ch in _OCR_LETTER_DIGITS]
        other_letters = len(letters) - len(suspicious)

        is_phone_like = (
            digits >= 4
            and other_letters == 0
            and bool(suspicious)
            and (digits + punct) >= (len(token) - len(suspicious))
        )
        if not is_phone_like:
            repaired_tokens.append(token)
            continue

        chars = list(token)
        token_ops: list[dict] = []
        for i, ch in enumerate(chars):
            if ch not in _OCR_LETTER_DIGITS:
                continue
            prev_ok = i == 0 or chars[i - 1].isdigit() or chars[i - 1] in _PHONE_PUNCT
            nxt_ok = i == len(chars) - 1 or chars[i + 1].isdigit() or chars[i + 1] in _PHONE_PUNCT
            if prev_ok or nxt_ok:
                token_ops.append({
                    "char": ch,
                    "position": i,
                    "replacement": _OCR_LETTER_DIGITS[ch],
                    "token": token,
                })
                chars[i] = _OCR_LETTER_DIGITS[ch]
        if token_ops:
            operations.extend(token_ops)
        repaired_tokens.append("".join(chars))

    if operations:
        warnings.append("ocr_repair_applied")
    return OcrPhoneRepair(
        original=raw,
        repaired=" ".join(repaired_tokens),
        operations=operations,
        confidence=1.0 if operations else 0.0,
        ambiguous=False,
        warnings=warnings,
    )


# ═══════════════════════════════════════════════════════════
# Phone parser
# ═══════════════════════════════════════════════════════════

# Minimum lengths for phone comparison
_MIN_FULL_COMPARISON_DIGITS = 7    # Minimum length to call two numbers "comparable"
_MIN_SUFFIX_DIGITS = 7             # Last 7 for suffix matching
_MIN_VALID_DIGITS = 6              # Absolute minimum to even consider


def _parse_extension(raw: str) -> tuple[str, str]:
    """Separate extension from primary number.

    Returns (primary_number, extension_digits).

    Safety: the bare "x" marker is ambiguous (it can appear in narrative text
    such as "box 12 x 3"). It is only accepted as an extension when the
    primary part is clearly a phone number (at least 6 digits). Unambiguous
    markers (ext, ext., extension, poste) are always accepted.
    """
    match = _EXTENSION_PATTERN.search(raw)
    if match:
        marker = match.group("marker")
        ext_digits = match.group("digits")
        primary = raw[:match.start()].strip()
        bare_x = marker.lower() == "x"
        if bare_x and sum(1 for ch in primary if ch.isdigit()) < 6:
            # Narrative "x" — not an extension
            return raw, ""
        return primary, ext_digits
    return raw, ""


def parse_phone(
    raw_value: str,
    *,
    source_span_start: int | None = None,
    source_span_end: int | None = None,
) -> ParsedPhone:
    """Parse a raw phone string into a deterministic representation.

    The core parser performs NO alphabetic OCR substitution. Use
    ``parse_phone_with_ocr`` when OCR-tolerant parsing is required.

    Handles:
    - Unicode digit normalization (Arabic-Indic, Eastern Arabic-Indic)
    - Directional control removal
    - Arabic punctuation normalization
    - + and 00 prefix detection (00 requires a credible international structure)
    - Extension separation (ext, ext., extension, x, poste)
    - Country code recognition ONLY from explicit prefixes

    Never infers country codes. Never assumes locale.
    """
    steps: list[str] = []
    warnings: list[str] = []
    original = raw_value

    # Step 0: Guard empty input
    if not raw_value or not raw_value.strip():
        return ParsedPhone(
            raw_value=raw_value,
            is_valid=False,
            warnings=["empty_value"],
            normalization_steps=["empty_input"],
        )

    # Step 1: Remove directional controls (derived, not raw)
    bidi_result = remove_directional_controls(raw_value)
    cleaned = bidi_result.cleaned_value
    if bidi_result.count_removed > 0:
        steps.append(f"removed_{bidi_result.count_removed}_bidi_controls")

    # Step 2: Normalize Arabic punctuation
    punct_result = normalize_arabic_punctuation(cleaned)
    cleaned = punct_result.normalized_value
    if punct_result.replacements:
        steps.append("normalized_arabic_punctuation")

    # Step 3: Detect digit systems before normalization
    from app.services.unicode_normalizer import normalize_digits as nd
    digit_result = nd(cleaned)
    original_digit_systems = [str(ds) for ds in digit_result.systems_detected]

    # Step 4: Separate extension BEFORE digit normalization
    primary_part, extension = _parse_extension(cleaned)
    if extension:
        steps.append("extension_separated")

    # Step 4b: Reject alphabetic characters in the primary part. A clean phone
    # value contains only digits, phone punctuation, and an optional explicit
    # prefix. Letters (e.g. OCR 'l'/'O') indicate corruption; the core parser
    # must NOT silently drop them — silently discarding a letter could
    # manufacture a plausible number out of corrupted input and let an
    # OCR-corrupted value masquerade as a clean full match. OCR-tolerant
    # callers repair first via parse_phone_with_ocr; unrepairable values fail
    # closed (is_valid=False). Extension marker letters (ext/x) were already
    # separated in Step 4 and do not reach this check.
    letters_present = any(ch.isalpha() for ch in primary_part)
    if letters_present:
        warnings.append("non_digit_characters_present")

    # Step 5: Normalize digits to ASCII (primary part only)
    normalized = normalize_digits_only(primary_part)
    if digit_result.conversion_occurred:
        steps.append("digits_normalized")

    # Step 6: Detect explicit prefix
    has_plus = normalized.startswith("+")
    has_double_zero = normalized.startswith("00") and not normalized.startswith("00", 2)
    # A leading "00" is only an international prefix when the remaining
    # structure is credible (at least MIN_INTERNATIONAL_AFTER_00 digits).
    if has_double_zero:
        after_00 = normalized[2:]
        if len(after_00) < _MIN_INTERNATIONAL_AFTER_00:
            has_double_zero = False
            warnings.append("leading_00_not_international")

    if has_plus:
        explicit_prefix = PhonePrefix.plus
        digits_only = normalized[1:]  # Strip the +
    elif has_double_zero and len(normalized) >= 4:
        explicit_prefix = PhonePrefix.double_zero
        digits_only = normalized[2:]  # Strip the 00
    else:
        explicit_prefix = PhonePrefix.none
        digits_only = normalized

    # Step 7: Extract only digits (NO alphabetic OCR substitution here)
    normalized_digits = re.sub(r"[^0-9]", "", digits_only)

    # Step 8: Try to extract country code from explicit prefix (recognition only)
    country_code, national_number = _try_extract_country_code(
        normalized_digits, explicit_prefix
    )
    if explicit_prefix != PhonePrefix.none and not country_code:
        warnings.append("country_code_not_recognized")

    # Step 9: Validate
    digit_len = len(normalized_digits)
    is_complete = (
        explicit_prefix != PhonePrefix.none
        and len(national_number) >= _MIN_FULL_COMPARISON_DIGITS
    )
    is_valid = digit_len >= _MIN_VALID_DIGITS and not letters_present

    if digit_len < _MIN_VALID_DIGITS:
        warnings.append(f"too_few_digits:{digit_len}")

    if extension and not normalized_digits:
        warnings.append("extension_only")

    return ParsedPhone(
        raw_value=raw_value,
        original_digit_systems=original_digit_systems,
        normalized_digits=normalized_digits,
        explicit_prefix=explicit_prefix,
        explicit_prefix_digits=country_code,
        country_code=country_code,
        national_number=national_number,
        extension=extension,
        has_plus=has_plus,
        has_double_zero=has_double_zero,
        is_valid=is_valid,
        is_complete=is_complete,
        warnings=warnings,
        normalization_steps=steps,
    )


def parse_phone_with_ocr(
    raw_value: str,
    *,
    source_span_start: int | None = None,
    source_span_end: int | None = None,
) -> ParsedPhone:
    """Parse a phone value applying the conservative OCR repair stage first.

    Raw evidence remains the original string. Every repair operation is
    recorded in ``ocr_repairs``; the comparison layer uses this flag to
    distinguish clean exact matches from OCR-assisted matches.
    """
    repair = ocr_repair_phone(raw_value)
    if not repair.operations:
        return parse_phone(raw_value)

    parsed = parse_phone(repair.repaired)
    steps = list(parsed.normalization_steps) + ["ocr_repair_applied"]
    return dataclasses.replace(
        parsed,
        raw_value=raw_value,
        ocr_repairs=repair.operations,
        normalization_steps=steps,
    )


# ═══════════════════════════════════════════════════════════
# Phone comparison (Phase 9R semantics)
# ═══════════════════════════════════════════════════════════

def compare_parsed_phones(
    left: ParsedPhone,
    right: ParsedPhone,
) -> tuple[PhoneComparisonOutcome, str]:
    """Compare two parsed phone representations.

    Returns (outcome, reason_code).

    Semantics:
    * Two explicit international numbers are compared by their COMPLETE
      international digit sequences. When the sequences differ and both are
      complete enough, the result is a conflict — never a shared-suffix match.
    * Country-code recognition is optional structure; it is never required
      for equality and never downgrades a value.
    * One explicit international number and one complete local number are
      compatible when the national number equals the local number.
    * Clean exact matches and OCR-assisted matches are distinct outcomes.
    """
    # ── Validation guards ──
    if not left.is_valid or not right.is_valid:
        return PhoneComparisonOutcome.insufficient, "phone_insufficient_digits"

    ld = left.normalized_digits
    rd = right.normalized_digits

    if not ld or not rd:
        return PhoneComparisonOutcome.insufficient, "phone_no_digits"

    left_intl = left.explicit_international
    right_intl = right.explicit_international
    ocr_involved = left.has_ocr_repair or right.has_ocr_repair

    # ── Both explicitly international: full-sequence comparison ──
    if left_intl and right_intl:
        if ld == rd:
            if left.explicit_prefix != right.explicit_prefix:
                # +X... == 00X...
                if ocr_involved:
                    return PhoneComparisonOutcome.ocr_assisted_compatible, "phone_ocr_intl_prefix_equivalent"
                return PhoneComparisonOutcome.intl_prefix_equivalent, "phone_intl_prefix_equivalent"
            if ocr_involved:
                return PhoneComparisonOutcome.ocr_assisted_compatible, "phone_ocr_exact"
            return PhoneComparisonOutcome.exact_match, "phone_exact_match"
        # Different complete international sequences: conflict when comparable.
        if len(ld) >= _MIN_FULL_COMPARISON_DIGITS and len(rd) >= _MIN_FULL_COMPARISON_DIGITS:
            return PhoneComparisonOutcome.conflict, "phone_intl_digits_conflict"
        return PhoneComparisonOutcome.insufficient, "phone_intl_too_short_for_comparison"

    # ── One explicit international, one local ──
    if left_intl != right_intl:
        explicit, local = (left, right) if left_intl else (right, left)
        if explicit.country_code and explicit.national_number:
            nat = explicit.national_number
            if nat == local.normalized_digits and len(nat) >= _MIN_SUFFIX_DIGITS:
                if ocr_involved:
                    return PhoneComparisonOutcome.ocr_assisted_compatible, "phone_ocr_compatible_local_intl"
                return PhoneComparisonOutcome.compatible_local_intl, "phone_compatible_local_intl"
            if (
                len(nat) >= _MIN_SUFFIX_DIGITS
                and len(local.normalized_digits) >= _MIN_SUFFIX_DIGITS
                and nat[-_MIN_SUFFIX_DIGITS:] == local.normalized_digits[-_MIN_SUFFIX_DIGITS:]
            ):
                return PhoneComparisonOutcome.weak_suffix_overlap, "phone_weak_suffix"
            return PhoneComparisonOutcome.insufficient, "phone_local_intl_not_comparable"
        # Explicit calling code unknown: only a conservative suffix overlap is possible.
        if (
            len(ld) >= _MIN_SUFFIX_DIGITS
            and len(rd) >= _MIN_SUFFIX_DIGITS
            and ld[-_MIN_SUFFIX_DIGITS:] == rd[-_MIN_SUFFIX_DIGITS:]
        ):
            return PhoneComparisonOutcome.weak_suffix_overlap, "phone_weak_suffix"
        return PhoneComparisonOutcome.insufficient, "phone_unknown_cc_not_comparable"

    # ── Both local ──
    if ld == rd:
        if ocr_involved:
            return PhoneComparisonOutcome.ocr_assisted_compatible, "phone_ocr_exact"
        return PhoneComparisonOutcome.exact_match, "phone_exact_match"
    if len(ld) >= _MIN_FULL_COMPARISON_DIGITS and len(rd) >= _MIN_FULL_COMPARISON_DIGITS:
        return PhoneComparisonOutcome.conflict, "phone_mismatch"
    if (
        len(ld) >= _MIN_SUFFIX_DIGITS
        and len(rd) >= _MIN_SUFFIX_DIGITS
        and ld[-_MIN_SUFFIX_DIGITS:] == rd[-_MIN_SUFFIX_DIGITS:]
    ):
        return PhoneComparisonOutcome.weak_suffix_overlap, "phone_weak_suffix"

    return PhoneComparisonOutcome.insufficient, "phone_insufficient_for_comparison"
